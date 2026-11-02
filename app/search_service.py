def build_study_query(
        search_text=None,
        status=None,
        min_participants=None,
):
    must = []
    filters = []

    if search_text:
        must.append({
            "match": {
                "title": search_text
            }
        })

    if status:
        filters.append({
            "term": {
                "status": status
            }
        })

    if min_participants is not None:
        filters.append({
            "range": {
                "participant_count": {
                    "gte": min_participants
                }
            }
        })

    if not must and not filters:
        return {"match_all": {}}

    bool_query = {}
    if must:
        bool_query["must"] = must
    if filters:
        bool_query["filter"] = filters

    return {"bool": bool_query}


def search_studies(
        client, search_text=None,
        status=None, min_participants=None,
        sort_by=None, order='desc',
        page=1, page_size=10
):
    query = build_study_query(search_text, status, min_participants)
    search_body = {
        'query': query,
        'from': (page - 1) * page_size,
        'size': page_size,
        'track_total_hits': True
    }
    allowed_sort_fields = ['participant_count', 'study_id']

    if sort_by in allowed_sort_fields:
        search_body['sort'] = [
            {sort_by: {'order': order}},
        ]

    result = client.search(index='studies_v2', body=search_body)

    total = result['hits']['total']['value']
    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'studies': [
            hit['_source']
            for hit in result['hits']['hits']
        ]
    }