import sys
sys.stdout.reconfigure(encoding="utf-8")

from src.core.pipeline import run

query = "Покажи динамику инфляции в России (индекс потребительских цен) за 2014–2024 годы, годовые значения."
print(f"Query: {query}\n")

result = run(query, top_k_retrieval=20, top_k_rerank=5, generate_code=True, use_full_registry=True)

status = result["status"]
p = result["extracted_params"]
print(f"status={status}  type={p.get('query_type')}  indicators={p.get('indicators')}  geo={p.get('geography')}  period={p.get('time_period')}")

if status == "needs_clarification":
    print("\nНЕОБХОДИМО УТОЧНЕНИЕ:")
    for q in result.get("clarifying_questions", []):
        print(f"  • {q}")

elif status == "validation_failed":
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
