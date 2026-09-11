from needs_agent import NeedsFoodRepository, QUESTION_GROUPS, batch_snapshot, risk_label, user_question_history

def test_cockpit_helpers(tmp_path):
    repo=NeedsFoodRepository(tmp_path/"demo.db")
    snap=batch_snapshot(repo,"B-20260903-M002-02")
    assert snap["batch"]["status"]=="지연"
    assert risk_label(snap)[0] in {"주의","높음"}
    assert sum(map(len,QUESTION_GROUPS.values()))==30
    assert user_question_history([{"role":"user","content":"레시피","created_at":"10:00"}])[0]["content"]=="레시피"
