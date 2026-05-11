import sys
sys.stdout.reconfigure(encoding="utf-8")

from src.core.pipeline import run

query = sys.argv[1] if len(sys.argv) > 1 else "Динамика ВВП России на душу населения за 2010-2023 годы"
print(f"Query: {query}\n")

result = run(query, top_k_retrieval=20, top_k_rerank=5, generate_code=True, execute_code=True, use_full_registry=True)

status = result["status"]
p = result["extracted_params"]
print(f"status={status}  type={p.get('query_type')}  indicators={p.get('indicators')}  geo={p.get('geography')}  period={p.get('time_period')}")

if status == "needs_clarification":
    print("\nНЕОБХОДИМО УТОЧНЕНИЕ:")
    for q in result.get("clarifying_questions", []):
        print(f"  • {q}")

elif status == "validation_failed":
    plan = result.get("assembly_plan", {})
    print("\n" + "="*60)
    print("ASSEMBLY PLAN (до валидации)")
    print("="*60)
    print(f"strategy: {plan.get('combination_strategy')}")
    for s in plan.get("primary_sources", []):
        print(f"  USE  [{s.get('role')}] {s.get('dataset_id')}  years={s.get('years_used')}  filters={s.get('filters')}")
        print(f"       {s.get('reason','')[:100]}")
    for s in plan.get("rejected_sources", []):
        print(f"  SKIP {s.get('dataset_id')}  — {s.get('reason','')[:100]}")
    print(f"output_columns: {[c.get('name') for c in plan.get('output_columns', [])]}")
    print("\nВАЛИДАЦИЯ ПРОВАЛЕНА:")
    for err in result.get("validation_errors", []):
        print(f"  ✗ {err}")

elif status == "no_data":
    print(f"\nНЕТ ДАННЫХ: {result.get('reason', '')}")

else:  # ok
    print("\nTOP DATASETS:")
    for i, d in enumerate(result["datasets"], 1):
        print(f"  {i}. [{d['source']}] {d['title']}")
        print(f"     rerank={d.get('rerank_score',0):.2f}  {d.get('rerank_reason','')[:90]}")

    plan = result.get("assembly_plan", {})
    print("\n" + "="*60)
    print("ASSEMBLY PLAN")
    print("="*60)
    print(f"strategy: {plan.get('combination_strategy')}")
    for s in plan.get("primary_sources", []):
        print(f"  USE  [{s.get('role')}] {s.get('dataset_id')}  years={s.get('years_used')}  filters={s.get('filters')}")
        print(f"       {s.get('reason','')[:100]}")
    for s in plan.get("rejected_sources", []):
        print(f"  SKIP {s.get('dataset_id')}  — {s.get('reason','')[:100]}")
    print(f"output_columns: {[c.get('name') for c in plan.get('output_columns', [])]}")

    print("\n" + "="*60)
    print("GENERATED CODE")
    print("="*60)
    print(result.get("code", ""))

if result.get("session_dir"):
    print("\n" + "="*60)
    print(f"ARTIFACTS: {result['session_dir']}")
    print(f"session_id: {result.get('session_id')}")

exec_info = result.get("execution")
if exec_info:
    print("\n" + "="*60)
    print("EXECUTION")
    print("="*60)
    ok = exec_info.get("success", False)
    script_status = "OK" if ok else f"FAILED (code {exec_info['returncode']})"
    print(f"script: {script_status}")
    if exec_info.get("output_csv"):
        print(f"output_csv: {exec_info['output_csv']}")
    for err in exec_info.get("errors", []):
        print(f"  ✗ {err}")
    if exec_info.get("stdout"):
        print(f"stdout:\n{exec_info['stdout'][:500]}")
    if not ok and exec_info.get("stderr"):
        print(f"stderr:\n{exec_info['stderr'][:1000]}")

    print("\n" + "="*60)
    print("OUTPUT VALIDATION")
    print("="*60)
    if exec_info.get("output_valid"):
        print("✓ Датасет прошёл проверку")
    else:
        print("✗ Проблемы с выходным датасетом:")
        for err in exec_info.get("output_validation_errors", []):
            print(f"  • {err}")
