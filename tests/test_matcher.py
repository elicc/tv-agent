from src.matcher import is_automatic, query_title, score
from src.models import Metadata, MovieIdentity


def test_query_title_removes_only_known_distribution_suffix() -> None:
    assert query_title("逃出绝命街（臻彩）") == "逃出绝命街"
    assert query_title("蓝光") == "蓝光"


def test_matcher_uses_available_identity_evidence() -> None:
    identity = MovieIdentity(
        source_instance_id="site",
        source_vod_id="1",
        title="灵境行者",
        year="2023",
        type="电视剧",
    )
    candidate = Metadata(
        external_id="36999847",
        external_type="tv",
        title="灵境行者",
        year="2023",
        type="剧情",
    )

    assert score(identity, candidate) > 0.9
    assert is_automatic(score(identity, candidate), 0.0)
