from rapidfuzz import process, fuzz


class SearchService:
    def __init__(self, employees):
        self.employees_list = employees

        self.by_id = {}
        for emp in employees:
            self.by_id.setdefault(emp.employee_id.upper(), []).append(emp)

        self.names_map = {}
        for emp in employees:
            self.names_map.setdefault(emp.name.upper(), []).append(emp)

    def search(self, query, limit=10):
        query = query.strip().upper()

        # ID Search
        if query in self.by_id:
            return [
                {
                    "employee": emp,
                    "score": 100,
                }
                for emp in self.by_id[query]
            ]

        # Prefix Match
        prefix_matches = []
        for emp in self.employees_list:
            if emp.name.upper().startswith(query):
                prefix_matches.append(
                    {
                        "employee": emp,
                        "score": 100,
                    }
                )
        
        if prefix_matches:
            return prefix_matches[:limit]

        # Fuzzy Search
        results = process.extract(
            query,
            self.names_map.keys(),
            scorer=fuzz.partial_ratio,
            limit=limit,
        )

        final_results = []
        for name, score, _ in results:
            if score >= 60:
                for emp in self.names_map[name]:
                    final_results.append({
                        "employee": emp,
                        "score": score
                    })

        return final_results[:limit]