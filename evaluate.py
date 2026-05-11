import sys
sys.stdout.reconfigure(encoding="utf-8")

import time
from pathlib import Path
from src.core.pipeline import run

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "id": "simple_cpi_russia",
        "name": "ИПЦ России 2014–2024",
        "category": "simple",
        "query": "Покажи динамику инфляции в России (индекс потребительских цен) за 2014–2024 годы, годовые значения.",
        "expected_status": "ok",
        "expected_type": "simple",
        "criteria": {
            "status_ok": True,
            "type_match": "simple",
            "indicators_contain": ["ИПЦ", "инфляц", "cpi", "consumer", "потребит"],
            "geo_russia": True,
            "execute": True,
            "min_rows": 8,
        },
    },
    {
        "id": "comparative_rd",
        "name": "Расходы на НИОКР",
        "category": "comparative",
        "query": "Сравни долю расходов на НИОКР в ВВП в России, Китае, Германии и США за 2015–2023.",
        "expected_status": "ok",
        "expected_type": "comparative",
        "criteria": {
            "status_ok": True,
            "type_match": "comparative",
            "indicators_contain": ["НИОКР", "R&D", "research", "разработ"],
            "execute": True,
            "min_rows": 10,
        },
    },
    {
        "id": "research_urbanization",
        "name": "Урбанизация и рождаемость",
        "category": "research",
        "query": "Как связан уровень урбанизации и рождаемость по странам мира?",
        "expected_status": "ok",
        "expected_type": "research",
        "criteria": {
            "status_ok": True,
            "type_match": "research",
            "indicators_contain": ["урбан", "рождаем", "urban", "fertil"],
            "execute": True,
            "min_rows": 50,
        },
    },
    {
        "id": "derived_real_income",
        "name": "Реальные доходы РФ",
        "category": "derived",
        "query": "Покажи реальные располагаемые доходы населения России с поправкой на инфляцию, индекс к 2014 году = 100.",
        "expected_status": "ok",
        "expected_type": "derived_metric",
        "criteria": {
            "status_ok": True,
            "type_match": "derived_metric",
            "indicators_contain": ["доход", "инфляц", "income", "real"],
            "geo_russia": True,
            "execute": True,
            "min_rows": 5,
        },
    },
    {
        "id": "ambiguous_inflation",
        "name": "Неоднозначный запрос про инфляцию",
        "category": "ambiguous",
        "query": "Дай данные по инфляции.",
        "expected_status": "needs_clarification",
        "criteria": {
            "status_clarification": True,
            "has_questions": True,
            "min_questions": 2,
        },
    },
    {
        "id": "no_data_dprk",
        "name": "Зарплаты IT в КНДР",
        "category": "no_data",
        "query": "Дай данные о зарплатах в IT-секторе Северной Кореи (КНДР) за 2020–2024 годы.",
        "expected_status": "no_data",
        "criteria": {
            "status_no_data": True,
            "has_reason": True,
        },
    },
]


# ---------------------------------------------------------------------------
# Criteria checkers
# ---------------------------------------------------------------------------

def _indicators_str(result: dict) -> str:
    p = result.get("extracted_params") or {}
    inds = p.get("indicators") or []
    return " ".join(str(i).lower() for i in inds)


def check(tc: dict, result: dict) -> list[tuple[str, bool, str]]:
    """Return list of (criterion_name, passed, detail)."""
    checks: list[tuple[str, bool, str]] = []
    c = tc.get("criteria", {})
    status = result.get("status", "")

    if c.get("status_ok"):
        ok = status == "ok"
        checks.append(("status=ok", ok, status))

    if c.get("status_clarification"):
        ok = status == "needs_clarification"
        checks.append(("status=needs_clarification", ok, status))

    if c.get("status_no_data"):
        ok = status == "no_data"
        checks.append(("status=no_data", ok, status))

    if c.get("type_match"):
        actual = (result.get("extracted_params") or {}).get("query_type", "")
        ok = actual == c["type_match"]
        checks.append((f"type={c['type_match']}", ok, actual))

    if c.get("indicators_contain"):
        inds = _indicators_str(result)
        matched = any(kw.lower() in inds for kw in c["indicators_contain"])
        checks.append(("indicators_match", matched, inds[:80] or "—"))

    if c.get("geo_russia"):
        p = result.get("extracted_params") or {}
        geo = " ".join(str(g).lower() for g in (p.get("geography") or []))
        ok = any(kw in geo for kw in ["russia", "рф", "россия", "russian"])
        checks.append(("geo=Russia", ok, geo[:60] or "—"))

    if c.get("has_questions"):
        qs = result.get("clarifying_questions") or []
        ok = len(qs) >= c.get("min_questions", 1)
        checks.append((f"questions≥{c.get('min_questions',1)}", ok, f"{len(qs)} questions"))

    if c.get("has_reason"):
        reason = result.get("reason", "")
        ok = bool(reason)
        checks.append(("has_reason", ok, (reason or "")[:80]))

    if c.get("execute") and status == "ok":
        exec_info = result.get("execution") or {}
        script_ok = exec_info.get("success", False)
        checks.append(("script_ok", script_ok, "exit=" + str(exec_info.get("returncode", "?"))))

        csv_path = exec_info.get("output_csv")
        checks.append(("output_csv_exists", bool(csv_path), str(csv_path or "—")))

        output_valid = exec_info.get("output_valid", False)
        checks.append(("output_valid", output_valid, str(exec_info.get("output_validation_errors", []))))

        if script_ok and csv_path and c.get("min_rows"):
            import pandas as pd
            try:
                df = pd.read_csv(csv_path)
                ok = len(df) >= c["min_rows"]
                checks.append((f"rows≥{c['min_rows']}", ok, f"{len(df)} rows"))
            except Exception as e:
                checks.append((f"rows≥{c['min_rows']}", False, str(e)))

    return checks


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_case(tc: dict) -> tuple[dict, float, str]:
    t0 = time.time()
    try:
        result = run(
            tc["query"],
            top_k_retrieval=20,
            top_k_rerank=5,
            generate_code=True,
            execute_code=tc.get("criteria", {}).get("execute", False),
            use_full_registry=True,
        )
        elapsed = time.time() - t0
        return result, elapsed, ""
    except Exception as e:
        return {}, time.time() - t0, str(e)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)

    total_criteria = 0
    passed_criteria = 0
    case_results = []

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{len(TEST_CASES)}] {tc['name']} ({tc['category']})")
        print(f"  query: {tc['query'][:80]}")

        result, elapsed, error = run_case(tc)

        if error:
            print(f"  ERROR: {error}")
            case_results.append((tc, [], elapsed, error))
            continue

        checks = check(tc, result)
        case_results.append((tc, checks, elapsed, ""))

        for name, passed, detail in checks:
            mark = "✓" if passed else "✗"
            total_criteria += 1
            if passed:
                passed_criteria += 1
            print(f"  {mark} {name:<35} {detail}")

        # Show top datasets if status=ok
        if result.get("status") == "ok":
            datasets = result.get("datasets") or []
            if datasets:
                top = datasets[0]
                print(f"  → top dataset: [{top.get('source')}] {top.get('title','')[:60]}")

        print(f"  ⏱ {elapsed:.1f}s  |  status={result.get('status','?')}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for tc, checks, elapsed, error in case_results:
        if error:
            verdict = "ERROR"
        elif not checks:
            verdict = "SKIP"
        else:
            case_pass = sum(1 for _, p, _ in checks if p)
            case_total = len(checks)
            verdict = f"{case_pass}/{case_total}"
        print(f"  {tc['name']:<35} {verdict}  ({elapsed:.1f}s)")

    print(f"\nTotal criteria: {passed_criteria}/{total_criteria} passed")


if __name__ == "__main__":
    main()
