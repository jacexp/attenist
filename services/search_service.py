from rapidfuzz import process, fuzz
from database.database_service import DatabaseService


class SearchService:
    def __init__(self, employees=None, database_service=None):
        """
        Initialize SearchService with SQLite backend.
        
        Args:
            employees: Legacy parameter for backward compatibility (ignored)
            database_service: DatabaseService instance for SQLite queries
        """
        if database_service:
            self.database_service = database_service
        else:
            # Create default database service if none provided
            self.database_service = DatabaseService()
        
        # Legacy support - keep employees list for fallback if needed
        self.employees_list = employees or []

    def search(self, query, limit=10):
        """
        Search employees using SQLite database with fuzzy matching fallback.
        Returns results in the same format as the original implementation.
        """
        query = query.strip()
        
        if not query:
            return []

        try:
            # First, try exact SQLite search (fast)
            db_results = self.database_service.search_employees(query, limit * 2)
            
            if db_results:
                # Convert database results to Employee objects
                employee_objects = self.database_service.search_employees_as_objects(query, limit * 2)
                
                # Return in expected format
                results = []
                for emp in employee_objects:
                    # Calculate simple match score
                    query_upper = query.upper()
                    emp_id_upper = emp.employee_id.upper()
                    emp_name_upper = emp.name.upper()
                    
                    if query_upper == emp_id_upper:
                        score = 100
                    elif query_upper == emp_name_upper:
                        score = 100
                    elif emp_id_upper.startswith(query_upper):
                        score = 95
                    elif emp_name_upper.startswith(query_upper):
                        score = 95
                    elif query_upper in emp_id_upper:
                        score = 85
                    elif query_upper in emp_name_upper:
                        score = 85
                    else:
                        score = 75
                    
                    results.append({
                        "employee": emp,
                        "score": score,
                    })
                
                # Sort by score descending
                results.sort(key=lambda x: x["score"], reverse=True)
                
                if results:
                    return results[:limit]
            
            # If SQLite search didn't find good matches, try fuzzy search
            # Get more employees from database for fuzzy matching
            all_employees = self.database_service.search_employees("", limit * 5)  # Get broader set
            
            if all_employees:
                employee_objects = []
                names_map = {}
                by_id = {}
                
                for db_emp in all_employees:
                    # Convert to Employee object
                    emp_obj = self.database_service.get_employee_as_object(db_emp["emp_id"])
                    if emp_obj:
                        employee_objects.append(emp_obj)
                        # Build maps for fuzzy search
                        by_id.setdefault(emp_obj.employee_id.upper(), []).append(emp_obj)
                        names_map.setdefault(emp_obj.name.upper(), []).append(emp_obj)
                
                # Apply original fuzzy search logic
                return self._fuzzy_search(query.upper(), by_id, names_map, employee_objects, limit)
            
            return []
            
        except Exception as e:
            # Fallback to legacy behavior if database fails
            print(f"Database search failed, using fallback: {e}")
            if self.employees_list:
                return self._legacy_search(query, limit)
            return []

    def _fuzzy_search(self, query, by_id, names_map, employees_list, limit):
        """Apply fuzzy search logic similar to original implementation."""
        
        # ID Search
        if query in by_id:
            return [
                {
                    "employee": emp,
                    "score": 100,
                }
                for emp in by_id[query]
            ]

        # Prefix Match
        prefix_matches = []
        for emp in employees_list:
            if emp.name.upper().startswith(query):
                prefix_matches.append(
                    {
                        "employee": emp,
                        "score": 100,
                    }
                )
        
        if prefix_matches:
            return prefix_matches[:limit]

        # Fuzzy Search with rapidfuzz
        if names_map:
            results = process.extract(
                query,
                names_map.keys(),
                scorer=fuzz.partial_ratio,
                limit=limit,
            )

            final_results = []
            for name, score, _ in results:
                if score >= 60:
                    for emp in names_map[name]:
                        final_results.append({
                            "employee": emp,
                            "score": score
                        })

            return final_results[:limit]
        
        return []

    def _legacy_search(self, query, limit):
        """Legacy search implementation for fallback."""
        query = query.strip().upper()

        # Build legacy indexes
        by_id = {}
        for emp in self.employees_list:
            by_id.setdefault(emp.employee_id.upper(), []).append(emp)

        names_map = {}
        for emp in self.employees_list:
            names_map.setdefault(emp.name.upper(), []).append(emp)

        return self._fuzzy_search(query, by_id, names_map, self.employees_list, limit)