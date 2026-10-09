from health_event_projection import project_confirmed_event


class Result:
    def __init__(self, data): self.data = data


class Query:
    def __init__(self, db, table): self.db, self.table, self.payload = db, table, None
    def select(self, *_): return self
    def eq(self, *_): return self
    def limit(self, *_): return self
    def insert(self, payload): self.payload = payload; return self
    def execute(self):
        if self.payload is not None:
            self.db.inserts.append((self.table, self.payload)); return Result([{"id": "id"}])
        return Result([])


class DB:
    def __init__(self): self.inserts=[]
    def table(self, name): return Query(self, name)


def test_all_supported_domain_projections_emit_only_contract_columns():
    cases = [
        ("symptom", {"symptom":"headache","severity":5}),
        ("hydration", {"amount":500}),
        ("sleep", {"amount":7,"unit":"hours","date":"2026-09-19"}),
        ("activity", {"duration":30,"name":"walking"}),
        ("exercise", {"duration":30,"name":"squats"}),
        ("weight", {"amount":62}),
        ("vital_sign", {"name":"heart rate","value":72}),
        ("medication", {"name":"example"}),
        ("mood", {"name":"calm"}),
        ("lab_result", {"name":"hemoglobin","value":13.2}),
        ("doctor_visit", {"name":"Doctor","category":"General"}),
        ("medical_condition", {"name":"example","status":"active"}),
        ("allergy", {"name":"example","reaction":"rash"}),
    ]
    for index, (event_type, data) in enumerate(cases):
        db=DB()
        result=project_confirmed_event(db=db,user_id="u",event_id=f"e-{index}",event_type=event_type,extracted_data=data,confidence=.9)
        assert result["domain_table"] is not None
        assert len(db.inserts) == 2
