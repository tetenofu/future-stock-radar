
import pandas as pd
import numpy as np
import radar


def test_config_exists_and_loads():
    cfg = radar.load_config()
    assert "universe" in cfg
    assert "scoring_weights" in cfg
    assert cfg["safety"]["paper_only"] is True


def test_score_is_bounded():
    cfg = radar.load_config()

    idx = pd.date_range("2023-01-01", periods=260, freq="B")
    close = pd.Series(np.linspace(10, 20, len(idx)), index=idx)
    volume = pd.Series(500000, index=idx)

    df = pd.DataFrame({
        "Close": close,
        "Volume": volume
    })

    result = radar.score_symbol("TEST", df, cfg)

    assert result is not None
    assert 0 <= result["score"] <= 100


def test_bad_prices_rejected():
    cfg = radar.load_config()

    idx = pd.date_range("2024-01-01", periods=260, freq="B")
    df = pd.DataFrame({
        "Close": [0.0] * 260,
        "Volume": [1000] * 260
    }, index=idx)

    assert radar.score_symbol("BAD", df, cfg) is None
