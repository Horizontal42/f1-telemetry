import os
import shutil
import pytest
from telemetry.rename import lap_token_present, insert_lap_token, read_lap_number, rename_unprocessed


# --- insert_lap_token ---

@pytest.mark.parametrize("filename,lap,expected", [
    # float token found → insert before it
    ("zandvoort_P_74.152_ferrari.csv", 8, "zandvoort_P_L8_74.152_ferrari.csv"),
    # single non-float token → append
    ("weirdname.csv", 3, "weirdname_L3.csv"),
    # two non-float tokens, no float → insert at index 2 (after 2nd token)
    ("track_session.csv", 5, "track_session_L5.csv"),
    # extension preserved
    ("a_b_1.5.csv", 2, "a_b_L2_1.5.csv"),
])
def test_insert_lap_token(filename, lap, expected):
    assert insert_lap_token(filename, lap) == expected


# --- lap_token_present ---

@pytest.mark.parametrize("stem,expected", [
    ("a_L8_b", True),
    ("a_L8_b.csv", True),   # stem may include extension (function splits on '_')
    ("a_b", False),
    ("a_b.csv", False),
    ("a_L_b", False),       # L without digits
    ("L8", True),
    ("notoken", False),
])
def test_lap_token_present(stem, expected):
    assert lap_token_present(stem) == expected


# --- read_lap_number ---

def test_read_lap_number_sample(sample_path):
    assert read_lap_number(sample_path) == 7


def test_read_lap_number_truncated(truncated_path):
    assert read_lap_number(truncated_path) == 9


# --- rename_unprocessed ---

def test_rename_unprocessed_renames(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_P_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    results = rename_unprocessed([src])
    assert len(results) == 1
    r = results[0]
    assert r.status == "renamed"
    assert r.new is not None and "L7" in r.new
    assert os.path.exists(tmp_path / r.new)


def test_rename_unprocessed_skips_already_tagged(tmp_path, sample_path):
    # rename first so it has L7 in name
    src = str(tmp_path / "zandvoort_P_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    rename_unprocessed([src])
    # now run on the directory — only the renamed file is present, should be skipped
    results = rename_unprocessed([str(tmp_path)])
    assert all(r.status == "skipped" for r in results)


def test_rename_unprocessed_error_target_exists(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_P_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    # pre-create the destination so rename sees a conflict
    dest = str(tmp_path / "zandvoort_P_L7_74.074_ferrari.csv")
    shutil.copy(sample_path, dest)
    results = rename_unprocessed([src])
    assert len(results) == 1
    assert results[0].status == "error"


def test_rename_unprocessed_dir_target(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_P_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    results = rename_unprocessed([str(tmp_path)])
    assert len(results) == 1
    assert results[0].status == "renamed"
