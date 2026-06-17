import os
import shutil
import pytest
from telemetry.rename import (
    lap_token_present, insert_lap_token, session_token_present,
    insert_tokens, read_lap_number, read_session_type, read_metadata,
    rename_unprocessed,
)


# --- insert_lap_token (backward compat) ---

@pytest.mark.parametrize("filename,lap,expected", [
    ("zandvoort_P_74.152_ferrari.csv", 8, "zandvoort_P_L8_74.152_ferrari.csv"),
    ("weirdname.csv", 3, "weirdname_L3.csv"),
    ("track_session.csv", 5, "track_session_L5.csv"),
    ("a_b_1.5.csv", 2, "a_b_L2_1.5.csv"),
])
def test_insert_lap_token(filename, lap, expected):
    assert insert_lap_token(filename, lap) == expected


# --- lap_token_present ---

@pytest.mark.parametrize("stem,expected", [
    ("a_L8_b", True),
    ("a_L8_b.csv", True),
    ("a_b", False),
    ("a_b.csv", False),
    ("a_L_b", False),
    ("L8", True),
    ("notoken", False),
])
def test_lap_token_present(stem, expected):
    assert lap_token_present(stem) == expected


# --- session_token_present ---

@pytest.mark.parametrize("stem,expected", [
    ("zandvoort_P1_L7_74.074_ferrari", True),
    ("zandvoort_Q2_L3_ferrari", True),
    ("zandvoort_R_L1_ferrari", True),
    ("zandvoort_FP1_L5_ferrari", True),
    ("zandvoort_P_74.074_ferrari", False),   # bare P without digit not matched
    ("zandvoort_L7_74.074_ferrari", False),
    ("notoken", False),
])
def test_session_token_present(stem, expected):
    assert session_token_present(stem) == expected


# --- insert_tokens ---

@pytest.mark.parametrize("filename,session_type,lap,expected", [
    ("zandvoort_74.074_ferrari.csv", "P1", 7, "zandvoort_P1_L7_74.074_ferrari.csv"),
    ("zandvoort_P_74.074_ferrari.csv", "P1", 7, "zandvoort_P_P1_L7_74.074_ferrari.csv"),
    ("track_session.csv", "Q2", 3, "track_session_Q2_L3.csv"),
    ("weirdname.csv", "R", 1, "weirdname_R_L1.csv"),
])
def test_insert_tokens(filename, session_type, lap, expected):
    assert insert_tokens(filename, session_type, lap) == expected


# --- read_lap_number ---

def test_read_lap_number_sample(sample_path):
    assert read_lap_number(sample_path) == 7


def test_read_lap_number_truncated(truncated_path):
    assert read_lap_number(truncated_path) == 9


# --- read_session_type ---

def test_read_session_type_sample(sample_path):
    assert read_session_type(sample_path) == 'P1'


# --- read_metadata ---

def test_read_metadata_sample(sample_path):
    lap, event, track = read_metadata(sample_path)
    assert lap == 7
    assert event == 'P1'
    assert track != ''


# --- rename_unprocessed ---

def test_rename_unprocessed_renames(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    results = rename_unprocessed([src])
    assert len(results) == 1
    r = results[0]
    assert r.status == "renamed"
    assert r.new is not None and "L7" in r.new and "P1" in r.new
    assert os.path.exists(r.new)


def test_rename_unprocessed_skips_already_tagged(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    rename_unprocessed([src])
    results = rename_unprocessed([str(tmp_path)])
    assert all(r.status == "skipped" for r in results)


def test_rename_unprocessed_error_target_exists(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    dest = str(tmp_path / "zandvoort_P1_L7_74.074_ferrari.csv")
    shutil.copy(sample_path, dest)
    results = rename_unprocessed([src])
    assert len(results) == 1
    assert results[0].status == "error"


def test_rename_unprocessed_dir_target(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    results = rename_unprocessed([str(tmp_path)])
    assert len(results) == 1
    assert results[0].status == "renamed"


def test_rename_unprocessed_moves_to_races_dir(tmp_path, sample_path):
    src = str(tmp_path / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    races_dir = str(tmp_path / 'races')
    results = rename_unprocessed([src], races_dir=races_dir)
    assert len(results) == 1
    r = results[0]
    assert r.status == 'renamed'
    assert r.new is not None and 'P1' in r.new and 'L7' in r.new
    assert os.path.exists(r.new)
    assert r.new.startswith(races_dir)
    assert 'Practice' in r.new
    assert not os.path.exists(src)


def test_rename_unprocessed_moves_already_renamed(tmp_path, sample_path):
    """Already-renamed file in wrong folder gets moved to correct folder."""
    src = str(tmp_path / "zandvoort_P1_L7_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    races_dir = str(tmp_path / 'races')
    results = rename_unprocessed([src], races_dir=races_dir)
    assert len(results) == 1
    r = results[0]
    assert r.status == 'renamed'
    assert 'Practice' in r.new
    assert os.path.exists(r.new)
    assert not os.path.exists(src)


def test_rename_unprocessed_skips_already_in_place(tmp_path, sample_path):
    """File already in correct folder is skipped on second run."""
    src = str(tmp_path / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    races_dir = str(tmp_path / 'races')
    rename_unprocessed([src], races_dir=races_dir)
    results = rename_unprocessed([races_dir], races_dir=races_dir)
    assert all(r.status == 'skipped' for r in results)


def test_rename_unprocessed_walks_subdirs(tmp_path, sample_path):
    """With races_dir, scans subdirectories recursively."""
    sub = tmp_path / 'sub' / 'nested'
    sub.mkdir(parents=True)
    src = str(sub / "zandvoort_74.074_ferrari.csv")
    shutil.copy(sample_path, src)
    races_dir = str(tmp_path / 'races')
    results = rename_unprocessed([str(tmp_path)], races_dir=races_dir)
    assert len(results) == 1
    assert results[0].status == 'renamed'
    assert 'Practice' in results[0].new
