"""CLI for phase 1: connector health, manual import, note generation.

No command performs a purchase and none fetches from a marketplace whose access
has not been verified (D-003, CLAUDE.md principle 7).
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

from src.core.models import Condition, PriceObservation, PriceType
from src.core.money import round_money

from src.obsidian_sync.writer import DealNoteWriter
from src.paper.calibration import calibrate
from src.paper.records import (
    OutcomeType,
    PaperOutcome,
    PaperPrediction,
    prediction_from_opportunity,
)
from src.paper.watchlist import (
    DEFAULT_WATCHLIST,
    WatchItem,
    append_watch_items,
    from_observation,
    load_watchlist,
    watch_id,
)
from src.paper.store import (
    DEFAULT_OUTCOMES,
    DEFAULT_PREDICTIONS,
    PaperStoreError,
    open_watchlist,
    append_outcome,
    append_prediction,
    load_outcomes,
    load_predictions,
    pair_records,
)
from src.pricing.calculator import CostInputs, build_opportunity
from src.pricing.fx import latest_rate, load_rates, rate_to_eur
from src.pricing.observations import (
    ObservationError,
    append_observation,
    load_observations,
    observations_from_csv,
)
from src.pricing.market_matrix import build_matrix, render_table, spreads
from src.pricing.serbian_market import DEFAULT_RULES, estimate_resale
from src.products import match_listing, match_text, reconcile_with_llm
from src.scrapers import list_connectors
from src.scrapers.manual_import import import_file


def cmd_health(_: argparse.Namespace) -> int:
    for connector in list_connectors():
        print(json.dumps(connector.health_check(), ensure_ascii=False))
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    listing = import_file(args.path, args.marketplace, args.listing_id, args.url)
    print(listing.model_dump_json(indent=2))
    print("--- product match ---")
    print(match_listing(listing).model_dump_json(indent=2))
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    """Match free text against the catalog without touching money or the LLM."""
    print(match_text(args.text).model_dump_json(indent=2))
    return 0


def cmd_price(args: argparse.Namespace) -> int:
    """Estimate the Serbian resale price for one product from stored observations."""
    observations = load_observations(args.observations)
    estimate = estimate_resale(observations, args.product_id, condition=Condition(args.condition))
    print(estimate.model_dump_json(indent=2))
    if not estimate.is_usable:
        print(f"INSUFFICIENT_DATA: {', '.join(estimate.missing_inputs)}")
        return 1
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    """Manual file -> listing -> (optional LLM evaluation) -> opportunity -> note."""
    listing = import_file(args.path, args.marketplace, args.listing_id, args.url)

    # Deterministic identity first — the catalog, not the LLM, decides the chip.
    product_match = match_listing(listing)

    evaluation = None
    if args.evaluate:
        from src.deal_engine.evaluator import ListingEvaluator

        evaluation = reconcile_with_llm(product_match, ListingEvaluator().evaluate(listing))

    fx = None
    purchase_fx = None
    if args.expected_sale_rsd is not None:
        try:
            rates = load_rates()
            fx = latest_rate("EUR", "RSD", rates)
            if listing.currency and listing.currency.upper() != "EUR":
                purchase_fx = rate_to_eur(listing.currency, rates)
        except Exception as exc:  # InsufficientData and IO errors alike
            print(f"FX unavailable: {exc}")

    opportunity = build_opportunity(
        listing=listing,
        evaluation=evaluation,
        cost_inputs=CostInputs(
            shipping_eur=Decimal(args.shipping_eur) if args.shipping_eur else None,
            import_buffer_eur=Decimal(args.import_buffer_eur)
            if args.import_buffer_eur
            else None,
            is_import=args.marketplace != "kupujemprodajem",
            intermediary_fee_eur=Decimal(args.intermediary_fee_eur)
            if args.intermediary_fee_eur
            else None,
        ),
        expected_sale_rsd=Decimal(args.expected_sale_rsd)
        if args.expected_sale_rsd
        else None,
        eur_rsd=fx,
        purchase_fx=purchase_fx,
        product_match=product_match,
    )

    path = DealNoteWriter().write(opportunity, overwrite=args.overwrite)
    print(
        f"match={product_match.status.value} ({product_match.product_id or '-'}) "
        f"verdict={opportunity.verdict.value} risk={opportunity.risk_level.value}"
    )
    if product_match.notes:
        print(f"match note: {product_match.notes}")
    if opportunity.missing_inputs:
        print("missing: " + ", ".join(opportunity.missing_inputs))
    print(f"note: {path}")
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    """Append Serbian price observations — one from flags, or many from a CSV.

    This is the MANUAL collection path (D-003): the owner reads a real listing
    and records what it says. Nothing is fetched and nothing is inferred.
    """
    if args.csv:
        observations = observations_from_csv(args.csv)
        for observation in observations:
            append_observation(args.observations, observation)
        print(f"appended {len(observations)} observations to {args.observations}")
        return 0

    required = {
        "--product-id": args.product_id,
        "--price": args.price,
        "--marketplace": args.marketplace,
        "--listing-id": args.listing_id,
    }
    missing = [flag for flag, value in required.items() if not value]
    if missing:
        print("INSUFFICIENT_DATA: missing " + ", ".join(missing))
        return 2

    observed_at = (
        datetime.fromisoformat(args.observed_at)
        if args.observed_at
        else datetime.now(timezone.utc)
    )
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    observation = PriceObservation(
        product_id=args.product_id,
        price_amount=Decimal(args.price),
        currency=args.currency,
        price_type=PriceType(args.price_type),
        condition=Condition(args.condition),
        observed_at=observed_at,
        marketplace=args.marketplace,
        source_listing_id=args.listing_id,
        url=args.url,
        is_bundle=args.bundle,
    )
    append_observation(args.observations, observation)
    print(f"appended 1 observation to {args.observations}")
    return 0


def cmd_matrix(args: argparse.Namespace) -> int:
    """The same product across every observed market, plus the gross spreads.

    A spread is not profit: transport, fees and the legal side of selling across
    a border are not in this table, and outside the EU->RS corridor they are not
    decided at all. It shows where prices differ, not what to do about it.
    """
    observations = load_observations(args.observations)
    try:
        rates = load_rates()
    except Exception as exc:
        print(f"FX unavailable: {exc}")
        rates = []

    cells = build_matrix(
        observations,
        condition=Condition(args.condition),
        products=[args.product_id] if args.product_id else None,
        rates=rates,
    )
    print(render_table(cells))

    found = spreads(cells)
    if found:
        print()
        print("razlike u EUR (neto = bruto - 25 EUR prevoza, D-019):")
        for spread in found[: args.limit]:
            print("  " + spread.headline)
        print()
        print(
            "Neto je samo posle prevoza. Posrednik, carina, provizija platforme i "
            "porez nisu uracunati; van koridora EU->RS nisu ni odluceni (D-018)."
        )
    elif any(cell.is_usable for cell in cells):
        print()
        print("no comparable pair: only one market is usable, or a rate is missing")
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
    """Score a candidate and record the prediction. No purchase, ever (D-003).

    The resale side comes from the Serbian observation store, not from a number
    typed at the prompt: a paper trade is only worth measuring if the estimate
    under test is the one the engine would actually produce.
    """
    listing = import_file(args.path, args.marketplace, args.listing_id, args.url)
    product_match = match_listing(listing)

    evaluation = None
    if args.evaluate:
        from src.deal_engine.evaluator import ListingEvaluator

        evaluation = reconcile_with_llm(product_match, ListingEvaluator().evaluate(listing))

    product_id = args.product_id or product_match.product_id
    estimate = None
    if product_id:
        try:
            observations = load_observations(args.observations)
        except ObservationError as exc:
            # No store yet: the candidate is still recorded, as
            # INSUFFICIENT_DATA. A missing estimate is not a zero estimate.
            print(f"observations unavailable: {exc}")
            observations = None
        if observations is not None:
            estimate = estimate_resale(
                observations, product_id, condition=Condition(args.condition)
            )

    fx = None
    purchase_fx = None
    try:
        rates = load_rates()
        fx = latest_rate("EUR", "RSD", rates)
        # A domestic listing is priced in RSD, so the purchase side needs the
        # other direction of the same observed rate.
        if listing.currency and listing.currency.upper() != "EUR":
            purchase_fx = rate_to_eur(listing.currency, rates)
    except Exception as exc:
        print(f"FX unavailable: {exc}")

    opportunity = build_opportunity(
        listing=listing,
        evaluation=evaluation,
        cost_inputs=CostInputs(
            shipping_eur=Decimal(args.shipping_eur) if args.shipping_eur else None,
            import_buffer_eur=Decimal(args.import_buffer_eur)
            if args.import_buffer_eur
            else None,
            is_import=args.marketplace != "kupujemprodajem",
            intermediary_fee_eur=Decimal(args.intermediary_fee_eur)
            if args.intermediary_fee_eur
            else None,
        ),
        expected_sale_rsd=estimate,
        eur_rsd=fx,
        purchase_fx=purchase_fx,
        product_match=product_match,
    )

    prediction = prediction_from_opportunity(
        opportunity,
        product_id=product_id,
        match_status=product_match.status.value,
        estimate=estimate,
    )
    append_prediction(prediction, args.predictions)
    print(prediction.model_dump_json(indent=2))
    print(f"recorded: {prediction.prediction_id} -> {args.predictions}")
    if prediction.missing_inputs:
        print("missing: " + ", ".join(prediction.missing_inputs))
    return 0


def _feed_observation_store(
    prediction: "PaperPrediction | WatchItem",
    outcome: PaperOutcome,
    args: argparse.Namespace,
) -> None:
    """Turn an observed outcome back into a price observation.

    This is the only route by which SOLD data can ever enter the pricing engine:
    a watched listing that actually sells says what that market paid, which is
    exactly what an asking-only sample cannot know (PRICING-ENGINE.md).

    The observation is tagged with its own marketplace and nothing more. Keeping
    a German sale out of the Serbian sample is the estimator's job, not this
    one's — `PricingRules.resale_marketplaces` already does it, and duplicating
    the rule here would mean a foreign sale is simply thrown away instead of
    landing in its own market's cell.
    """
    if prediction.product_id is None:
        print("not recorded as an observation: subject has no product_id")
        return

    if outcome.outcome is OutcomeType.SOLD:
        amount = outcome.actual_sale_rsd or outcome.actual_sale_eur
        currency = "RSD" if outcome.actual_sale_rsd is not None else "EUR"
        price_type = PriceType.SOLD
    elif outcome.outcome is OutcomeType.PRICE_CUT:
        amount = outcome.new_asking_amount
        currency = (outcome.new_asking_currency or "").upper()
        price_type = PriceType.ASKING
    else:
        print(
            f"not recorded as an observation: {outcome.outcome.value} carries no "
            "observed price"
        )
        return

    if amount is None or not currency:
        print("not recorded as an observation: no observed price on this outcome")
        return

    observation = PriceObservation(
        product_id=prediction.product_id,
        price_amount=amount,
        currency=currency,
        price_type=price_type,
        condition=Condition(args.condition),
        observed_at=outcome.observed_at,
        marketplace=prediction.marketplace,
        source_listing_id=prediction.source_listing_id,
        url=prediction.url,
    )
    append_observation(args.observations, observation)
    print(
        f"recorded a {price_type.value} observation of {amount} {currency} "
        f"for {prediction.product_id} in {args.observations}"
    )


def cmd_outcome(args: argparse.Namespace) -> int:
    """Record what the market did. Only an observed sale carries a price."""
    subject_id = args.prediction_id
    predictions = _load_predictions_or_empty(args.predictions) or []
    matching = [p for p in predictions if p.prediction_id == subject_id]
    watched = [w for w in load_watchlist(args.watchlist) if w.watch_id == subject_id]

    if not matching and not watched:
        print(f"unknown subject: {subject_id} (neither a prediction nor a watch item)")
        return 2
    # A watch item carries no verdict, so it feeds the observation store only.
    prediction = matching[-1] if matching else None
    watch_item = watched[-1] if watched else None

    outcome_type = OutcomeType(args.outcome)
    sale_rsd = Decimal(args.sale_rsd) if args.sale_rsd else None
    sale_eur = Decimal(args.sale_eur) if args.sale_eur else None
    rate = None

    if sale_rsd is not None and sale_eur is None:
        try:
            fx = latest_rate("EUR", "RSD", load_rates())
        except Exception as exc:
            # Without a rate the EUR figure would have to be invented, and the
            # calibration report scores in EUR. Refuse instead (principle 1).
            print(f"INSUFFICIENT_DATA: sale price in RSD but no FX rate ({exc})")
            return 2
        rate = fx.rate
        sale_eur = round_money(sale_rsd / fx.rate)

    observed_at = (
        datetime.fromisoformat(args.observed_at)
        if args.observed_at
        else datetime.now(timezone.utc)
    )
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)

    outcome = PaperOutcome(
        prediction_id=args.prediction_id,
        outcome=outcome_type,
        observed_at=observed_at,
        actual_sale_rsd=sale_rsd,
        actual_sale_eur=sale_eur,
        eur_rsd_rate=rate,
        new_asking_amount=Decimal(args.new_asking) if args.new_asking else None,
        new_asking_currency=args.new_asking_currency if args.new_asking else None,
        days_listed=args.days_listed,
        source=args.source,
        notes=args.notes,
    )
    append_outcome(outcome, args.outcomes)
    print(outcome.model_dump_json(indent=2))
    if args.record_observation:
        subject = prediction or watch_item
        _feed_observation_store(subject, outcome, args)
    return 0


def _load_predictions_or_empty(path: str) -> list | None:
    """Predictions, or None after reporting that no store exists yet."""
    try:
        return load_predictions(path)
    except PaperStoreError as exc:
        if Path(path).exists():
            raise
        print(f"INSUFFICIENT_DATA: {exc}")
        return None


def _load_outcomes_or_empty(path: str) -> list:
    try:
        return load_outcomes(path)
    except PaperStoreError:
        if Path(path).exists():
            raise
        return []


def cmd_watch(args: argparse.Namespace) -> int:
    """Subjects still waiting for an outcome: predictions and watched listings.

    The watchlist is not only the deals worth buying. A listing priced too high
    that later sells anyway is the clearest evidence we get about what a market
    really pays, and a price cut is evidence the seller could not get it.
    """
    if args.add_market:
        return _watch_add(args)

    predictions = _load_predictions_or_empty(args.predictions) or []
    outcomes = _load_outcomes_or_empty(args.outcomes)
    items = load_watchlist(args.watchlist)

    now = datetime.now(timezone.utc)
    latest: dict[str, OutcomeType] = {}
    for outcome in outcomes:
        latest[outcome.prediction_id] = outcome.outcome

    prediction_ids = {prediction.prediction_id for prediction in predictions}
    prediction_outcomes = [o for o in outcomes if o.prediction_id in prediction_ids]

    rows: list[tuple[datetime, str, str]] = []

    for prediction, outcome in open_watchlist(pair_records(predictions, prediction_outcomes)):
        if args.marketplace and prediction.marketplace != args.marketplace:
            continue
        price = (
            f"{prediction.listing_price_amount} {prediction.listing_currency}"
            if prediction.listing_price_amount is not None
            else "UNKNOWN"
        )
        last = f", last seen {outcome.outcome.value}" if outcome else ""
        age = (now - prediction.predicted_at).days
        rows.append(
            (
                prediction.predicted_at,
                prediction.prediction_id,
                f"  {prediction.verdict.value:<18} {price:>12}  "
                f"{prediction.product_id or '-'}  ({age}d old{last})\n"
                f"  {prediction.title[:70]}\n  {prediction.url}",
            )
        )

    for item in items:
        if args.marketplace and item.marketplace != args.marketplace:
            continue
        seen = latest.get(item.watch_id)
        if seen in (OutcomeType.SOLD, OutcomeType.DELISTED):
            continue
        age = (now - item.first_seen_at).days
        last = f", last seen {seen.value}" if seen else ""
        rows.append(
            (
                item.first_seen_at,
                item.watch_id,
                f"  {'WATCHING':<18} "
                f"{f'{item.asking_amount} {item.asking_currency}':>12}  "
                f"{item.product_id}  ({age}d old{last})\n  {item.url or '-'}",
            )
        )

    if not rows:
        print("watchlist is empty")
        return 0

    rows.sort(key=lambda row: row[0])
    print(f"{len(rows)} subject(s) awaiting an outcome:")
    print()
    for _, subject_id, body in rows:
        print(subject_id)
        print(body)
    print()
    print(
        "Record what happened with:  arbitrage outcome --prediction-id <id> "
        "--outcome SOLD|PRICE_CUT|UNSOLD|DELISTED"
    )
    return 0


def _watch_add(args: argparse.Namespace) -> int:
    """Follow every current listing of one market, from the observation store."""
    observations = load_observations(args.observations)
    selected = [
        obs
        for obs in observations
        if obs.marketplace == args.add_market
        and (args.product_id is None or obs.product_id == args.product_id)
    ]
    if not selected:
        print(f"no observations for marketplace '{args.add_market}'")
        return 2

    added = append_watch_items(
        [from_observation(obs, reason=args.reason) for obs in selected], args.watchlist
    )
    print(
        f"{len(selected)} observation(s) considered, {len(added)} added to {args.watchlist}"
        + (" (rest already watched)" if len(added) < len(selected) else "")
    )
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Calibration report over stored paper trades (operations/PAPER-TRADING.md)."""
    # An empty store is a normal early state, not a corrupt one. A store that
    # exists but cannot be parsed still raises — that is a real problem.
    predictions = _load_predictions_or_empty(args.predictions)
    if predictions is None:
        return 1
    outcomes = _load_outcomes_or_empty(args.outcomes)
    prediction_ids = {prediction.prediction_id for prediction in predictions}
    prediction_outcomes = [o for o in outcomes if o.prediction_id in prediction_ids]

    report = calibrate(pair_records(predictions, prediction_outcomes))
    print(report.model_dump_json(indent=2))
    if not report.is_usable:
        print("INSUFFICIENT_DATA: " + ", ".join(report.missing_inputs))
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arbitrage", description="GPU arbitrage engine")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="connector access status").set_defaults(func=cmd_health)

    match_cmd = sub.add_parser("match", help="match free text against the catalog")
    match_cmd.add_argument("text")
    match_cmd.set_defaults(func=cmd_match)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("path", help="manually saved HTML file")
    common.add_argument("--marketplace", required=True)
    common.add_argument("--listing-id", required=True, dest="listing_id")
    common.add_argument("--url", required=True)

    imp = sub.add_parser("import", parents=[common], help="normalize a saved page")
    imp.set_defaults(func=cmd_import)

    price = sub.add_parser("price", help="estimate the Serbian resale price")
    price.add_argument("--product-id", dest="product_id", required=True)
    price.add_argument(
        "--observations",
        default="data/observations/serbia.jsonl",
        help="JSONL file of Serbian price observations",
    )
    price.add_argument("--condition", default="used", choices=["used", "new"])
    price.set_defaults(func=cmd_price)

    note = sub.add_parser("note", parents=[common], help="generate an Obsidian deal note")
    note.add_argument("--evaluate", action="store_true", help="run the LLM evaluator")
    note.add_argument("--shipping-eur", dest="shipping_eur")
    note.add_argument("--import-buffer-eur", dest="import_buffer_eur")
    note.add_argument(
        "--intermediary-fee-eur",
        dest="intermediary_fee_eur",
        help="EU intermediary fee in EUR; required for imports (D-010)",
    )
    note.add_argument("--expected-sale-rsd", dest="expected_sale_rsd")
    note.add_argument("--overwrite", action="store_true")
    note.set_defaults(func=cmd_note)

    # --- W6 paper trading ---------------------------------------------------
    observations_arg = argparse.ArgumentParser(add_help=False)
    observations_arg.add_argument(
        "--observations",
        default="data/observations/serbia.jsonl",
        help="JSONL file of Serbian price observations",
    )

    observe = sub.add_parser(
        "observe",
        parents=[observations_arg],
        help="append Serbian price observations (single or --csv)",
    )
    observe.add_argument("--csv", help="CSV file with many observations")
    observe.add_argument("--product-id", dest="product_id")
    observe.add_argument("--price", help="asking price in the listing currency")
    observe.add_argument("--currency", default="RSD")
    observe.add_argument("--price-type", dest="price_type", default="asking",
                         choices=[t.value for t in PriceType])
    observe.add_argument("--condition", default="used", choices=[c.value for c in Condition])
    observe.add_argument("--marketplace")
    observe.add_argument("--listing-id", dest="listing_id")
    observe.add_argument("--url")
    observe.add_argument("--observed-at", dest="observed_at", help="ISO timestamp; default now")
    observe.add_argument("--bundle", action="store_true", help="listing is a bundle")
    observe.set_defaults(func=cmd_observe)

    predictions_arg = argparse.ArgumentParser(add_help=False)
    predictions_arg.add_argument("--predictions", default=str(DEFAULT_PREDICTIONS))
    outcomes_arg = argparse.ArgumentParser(add_help=False)
    outcomes_arg.add_argument("--outcomes", default=str(DEFAULT_OUTCOMES))
    watchlist_arg = argparse.ArgumentParser(add_help=False)
    watchlist_arg.add_argument("--watchlist", default=str(DEFAULT_WATCHLIST))

    matrix = sub.add_parser(
        "matrix",
        parents=[observations_arg],
        help="price table across markets, with gross spreads",
    )
    matrix.add_argument("--product-id", dest="product_id", help="limit to one product")
    matrix.add_argument("--condition", default="used", choices=["used", "new"])
    matrix.add_argument("--limit", type=int, default=10, help="how many spreads to print")
    matrix.set_defaults(func=cmd_matrix)

    predict = sub.add_parser(
        "predict",
        parents=[common, observations_arg, predictions_arg],
        help="score a candidate and record the paper prediction",
    )
    predict.add_argument("--evaluate", action="store_true", help="run the LLM evaluator")
    predict.add_argument("--product-id", dest="product_id",
                         help="override the matched product for the resale estimate")
    predict.add_argument("--condition", default="used", choices=["used", "new"])
    predict.add_argument("--shipping-eur", dest="shipping_eur")
    predict.add_argument("--import-buffer-eur", dest="import_buffer_eur")
    predict.add_argument("--intermediary-fee-eur", dest="intermediary_fee_eur")
    predict.set_defaults(func=cmd_predict)

    outcome = sub.add_parser(
        "outcome",
        parents=[predictions_arg, outcomes_arg, watchlist_arg],
        help="record what the market did with a predicted listing",
    )
    outcome.add_argument(
        "--prediction-id",
        dest="prediction_id",
        required=True,
        help="prediction id or watch id",
    )
    outcome.add_argument("--outcome", required=True, choices=[o.value for o in OutcomeType])
    outcome.add_argument("--sale-rsd", dest="sale_rsd", help="observed sale price in RSD")
    outcome.add_argument("--sale-eur", dest="sale_eur", help="observed sale price in EUR")
    outcome.add_argument(
        "--new-asking",
        dest="new_asking",
        help="lowered asking price, for a PRICE_CUT outcome",
    )
    outcome.add_argument(
        "--new-asking-currency", dest="new_asking_currency", default="EUR"
    )
    outcome.add_argument(
        "--record-observation",
        action="store_true",
        help="also feed the observed price into the Serbian observation store",
    )
    outcome.add_argument(
        "--observations",
        default="data/observations/serbia.jsonl",
        help="observation store to feed with --record-observation",
    )
    outcome.add_argument(
        "--condition",
        default="used",
        choices=[c.value for c in Condition],
        help="condition to record on the fed observation",
    )
    outcome.add_argument("--days-listed", dest="days_listed", type=int)
    outcome.add_argument("--observed-at", dest="observed_at", help="ISO timestamp; default now")
    outcome.add_argument("--source", default="manual", help="how the outcome was observed")
    outcome.add_argument("--notes")
    outcome.set_defaults(func=cmd_outcome)

    watch = sub.add_parser(
        "watch",
        parents=[predictions_arg, outcomes_arg, watchlist_arg, observations_arg],
        help="subjects still waiting for an outcome, oldest first",
    )
    watch.add_argument("--marketplace", help="show only one marketplace")
    watch.add_argument(
        "--add",
        dest="add_market",
        help="follow every observed listing of this marketplace",
    )
    watch.add_argument("--product-id", dest="product_id", help="limit --add to one product")
    watch.add_argument("--reason", default="price_signal", help="why this market is watched")
    watch.set_defaults(func=cmd_watch)

    report = sub.add_parser(
        "report",
        parents=[predictions_arg, outcomes_arg],
        help="calibration report over stored paper trades",
    )
    report.set_defaults(func=cmd_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    # The Anthropic client reads ANTHROPIC_API_KEY from the environment, so the
    # .env file has to be loaded before any command runs. Values already set in
    # the shell win — .env never overrides an explicitly exported key.
    load_dotenv(override=False)
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
