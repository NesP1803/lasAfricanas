from .header_matcher import score_entity


def classify_sheet(sheet_name, headers):
    scores = score_entity(headers)
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_entity, top_score = sorted_scores[0]
    if len(sorted_scores) > 1 and (top_score - sorted_scores[1][1]) < 15:
        return 'ambigua', top_score, scores
    return top_entity, top_score, scores
