from pprint import pprint

from app.search_service import build_study_query


# Test 1: Search text only
query = build_study_query(search_text="diabetes")
pprint(query)

# Test 2: Status only
query = build_study_query(status="Completed")
pprint(query)

# Test 3: No parameters
query = build_study_query()
pprint(query)

# Test 4: All parameters
query = build_study_query(
    search_text="diabetes",
    status="Completed",
    min_participants=100
)
pprint(query)