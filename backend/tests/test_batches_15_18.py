from memory_knowledge_graph import build_knowledge_graph,memory_candidates
from indian_food_intelligence import lookup_food,search_foods
from advanced_cycle_intelligence import analyze_advanced
from fitness_intelligence import analyze_fitness
def test_memory_graph():
 e=[{"event_type":"sleep","extracted_data":{"hours":6},"created_at":"2026-01-01T00:00:00Z"}]*3
 assert build_knowledge_graph(e)["node_count"]>=1 and memory_candidates(e)[0]["memory_level"]=="L3"
def test_food(): assert lookup_food("chapati")["name"]=="roti" and search_foods("dosa")
def test_cycle():
 e=[{"event_type":"period","extracted_data":{"is_start":True,"date":"2026-01-01"}},{"event_type":"period","extracted_data":{"is_start":True,"date":"2026-01-29"}},{"event_type":"period","extracted_data":{"is_start":True,"date":"2026-02-26"}}]
 assert analyze_advanced(e)["observed_intervals"]==[28,28]
def test_fitness_empty(): assert "exercise/activity" in analyze_fitness([])["data_gaps"]
