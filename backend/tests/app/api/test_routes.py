from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from course_builder.lexicon import extract_kanji_chars
from db.session import get_db
from domain.auth.models import User, UserCourseEnrollment
from domain.content import audio_service
from domain.content.display import append_alternate_script_hint
from domain.content.models import (
    CourseVersion,
    Item,
    ItemKanjiKanaMatch,
    ItemSentenceTiles,
    ItemWordChoice,
    Kanji,
    KanjiIntroduction,
    Lesson,
    LessonSentence,
    Section,
    Sentence,
    SentenceAudioAsset,
    SentenceTile,
    SentenceTileSet,
    SentenceUnit,
    SentenceWordLink,
    Unit,
    Word,
    WordAudioAsset,
)
from domain.learning.models import ExamAttempt, UserLessonProgress
import main as app_main
from security import hash_password
from tests.app.course_builder.stages.assembly.test_hints_and_kanji_introductions import hints_test_config
from tests.helpers.builder import create_test_build_context
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.pipeline import build_publish_ready_course
from tests.helpers.scenarios import single_intro_unit_plan_payload


@pytest.fixture
def client(db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    context = create_test_build_context(db_session, tmp_path, content=hints_test_config())
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    course_version = db_session.get(CourseVersion, context.course_version_id)
    assert course_version is not None
    course_version.status = "active"

    first_lesson = db_session.scalar(select(Lesson).order_by(Lesson.order_index.asc()))
    assert first_lesson is not None
    first_word_id = db_session.scalar(
        select(Word.id)
        .join(SentenceWordLink, SentenceWordLink.word_id == Word.id)
        .join(Sentence, Sentence.id == SentenceWordLink.sentence_id)
        .where(Sentence.course_version_id == context.course_version_id)
        .order_by(Word.intro_order.asc())
        .limit(1)
    )
    assert first_word_id is not None
    db_session.add(Kanji(char="田", primary_meaning="rice field"))
    db_session.add(
        KanjiIntroduction(
            course_version_id=context.course_version_id,
            lesson_id=first_lesson.id,
            kanji_char="田",
            word_id=first_word_id,
            example_word_ja="田中",
            example_reading="たなか",
            meaning_en="Tanaka",
        )
    )
    db_session.commit()

    bind = db_session.get_bind()
    test_engine: Engine = bind.engine if isinstance(bind, Connection) else bind
    monkeypatch.setattr(app_main, "engine", test_engine)
    app = app_main.create_app()

    request_session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
        future=True,
    )

    def override_get_db() -> Generator[Session, None, None]:
        with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def kanji_client(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    context = create_test_build_context(
        db_session,
        tmp_path,
        content=build_test_config_yaml(),
    )
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    course_version = db_session.get(CourseVersion, context.course_version_id)
    assert course_version is not None
    course_version.status = "active"
    db_session.commit()

    bind = db_session.get_bind()
    test_engine: Engine = bind.engine if isinstance(bind, Connection) else bind
    monkeypatch.setattr(app_main, "engine", test_engine)
    app = app_main.create_app()

    request_session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
        future=True,
    )

    def override_get_db() -> Generator[Session, None, None]:
        with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def kana_client(
    db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    context = create_test_build_context(
        db_session,
        tmp_path,
        content=build_test_config_yaml(),
    )
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    course_version = db_session.get(CourseVersion, context.course_version_id)
    assert course_version is not None
    course_version.status = "active"
    db_session.commit()

    bind = db_session.get_bind()
    test_engine: Engine = bind.engine if isinstance(bind, Connection) else bind
    monkeypatch.setattr(app_main, "engine", test_engine)
    app = app_main.create_app()

    request_session_factory = sessionmaker(
        bind=db_session.get_bind(),
        autoflush=False,
        autocommit=False,
        future=True,
    )

    def override_get_db() -> Generator[Session, None, None]:
        with request_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


def _register_and_get_token(client: TestClient) -> str:
    response = client.post("/api/v1/auth/register", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_auth_content_learning_and_explain_endpoints(client: TestClient, db_session: Session) -> None:
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == "user@example.com"
    enrollment_id = me_data["enrollment_id"]
    assert enrollment_id is not None

    current_course_response = client.get("/api/v1/course/current", headers=headers)
    assert current_course_response.status_code == 200
    current_course = current_course_response.json()
    assert current_course["status"] == "active"

    path_response = client.get("/api/v1/path", headers=headers)
    assert path_response.status_code == 200
    path_data = path_response.json()
    assert path_data["sections"]
    current_unit_id = path_data["current_unit_id"]
    current_lesson_id = path_data["current_lesson_id"]
    assert current_unit_id is not None
    assert current_lesson_id is not None

    units_response = client.get("/api/v1/units", headers=headers)
    assert units_response.status_code == 200
    units_data = units_response.json()
    assert units_data

    unit_detail_response = client.get(f"/api/v1/units/{current_unit_id}", headers=headers)
    assert unit_detail_response.status_code == 200
    unit_detail = unit_detail_response.json()
    assert unit_detail["lessons"]

    next_item_response = client.get(
        f"/api/v1/lessons/{current_lesson_id}/next-item", headers=headers, params={"cursor": 0}
    )
    assert next_item_response.status_code == 200
    next_item = next_item_response.json()
    assert next_item["answer_tiles"]
    submitted_answer = next_item["answer_tiles"][0]

    submit_response = client.post(
        f"/api/v1/lessons/{current_lesson_id}/submit",
        headers=headers,
        json={"answers": [{"item_id": next_item["item_id"], "user_answer": submitted_answer}]},
    )
    assert submit_response.status_code == 200
    submit_data = submit_response.json()
    assert submit_data["lesson_id"] == current_lesson_id
    assert submit_data["progress_state"] == "in_progress"

    sentence_id = db_session.scalar(select(LessonSentence.sentence_id).limit(1))
    assert sentence_id is not None
    sentence_tokens_response = client.get(f"/api/v1/sentences/{sentence_id}/tokens", headers=headers)
    assert sentence_tokens_response.status_code == 200
    sentence_tokens = sentence_tokens_response.json()
    assert sentence_tokens["tokens"]

    token_surface = sentence_tokens["tokens"][0]["surface"]
    explain_response = client.post(
        "/api/v1/explain/token",
        headers=headers,
        json={"sentence_id": sentence_id, "token_surface": token_surface},
    )
    assert explain_response.status_code == 200
    assert explain_response.json()["matching_tokens"]

    progress = db_session.get(UserLessonProgress, {"enrollment_id": enrollment_id, "lesson_id": current_lesson_id})
    assert progress is not None
    assert progress.state == "in_progress"

    kanji_lessons_response = client.get("/api/v1/kanji/lessons", headers=headers)
    assert kanji_lessons_response.status_code == 200
    kanji_lessons = kanji_lessons_response.json()
    assert kanji_lessons["lessons"]

    kanji_detail_response = client.get("/api/v1/kanji/田", headers=headers)
    assert kanji_detail_response.status_code == 200
    assert kanji_detail_response.json()["kanji_char"] == "田"


def test_sqladmin_requires_admin_login(client: TestClient) -> None:
    response = client.get("/admin/", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin/login" in response.headers["location"]


def test_sqladmin_allows_admin_user_login(client: TestClient, db_session: Session) -> None:
    bind = db_session.get_bind()
    admin_bind = bind.engine if isinstance(bind, Connection) else bind
    admin_session_factory = sessionmaker(
        bind=admin_bind,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    with admin_session_factory() as admin_session:
        admin_session.add(
            User(
                email="admin@example.com",
                password_hash=hash_password("password123"),
                is_admin=True,
            )
        )
        admin_session.commit()

    login_page_response = client.get("/admin/login")
    assert login_page_response.status_code == 200

    login_response = client.post(
        "/admin/login",
        data={"username": "admin@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    admin_response = client.get("/admin/", follow_redirects=False)
    assert admin_response.status_code == 200


def test_sqladmin_can_set_and_unset_unit_completion(client: TestClient, db_session: Session) -> None:
    bind = db_session.get_bind()
    admin_bind = bind.engine if isinstance(bind, Connection) else bind
    admin_session_factory = sessionmaker(
        bind=admin_bind,
        autoflush=False,
        autocommit=False,
        future=True,
    )
    with admin_session_factory() as admin_session:
        admin = User(
            email="admin2@example.com",
            password_hash=hash_password("password123"),
            is_admin=True,
        )
        learner = User(
            email="learner2@example.com",
            password_hash=hash_password("password123"),
        )
        active_course = CourseVersion(
            code="admin-test",
            version=1,
            build_version=1,
            status="active",
            config_version="test",
            config_hash="test-hash",
        )
        admin_session.add_all([admin, learner, active_course])
        admin_session.flush()
        section = Section(
            course_version_id=active_course.id,
            code="ADMIN_TEST",
            order_index=1,
            title="Admin Test Section",
            description="Admin test section",
            generation_description="Admin test section",
            target_unit_count=1,
            target_new_word_count=0,
        )
        admin_session.add(section)
        admin_session.flush()
        unit = Unit(
            section_id=section.id,
            order_index=1,
            title="Admin Test Unit",
            description="Admin test unit",
        )
        admin_session.add(unit)
        admin_session.flush()
        lessons = [
            Lesson(unit_id=unit.id, order_index=1, kind="normal", force_kana_display=False, target_item_count=1),
            Lesson(unit_id=unit.id, order_index=2, kind="review_previous_units", force_kana_display=False, target_item_count=1),
            Lesson(unit_id=unit.id, order_index=3, kind="exam", force_kana_display=False, target_item_count=1),
        ]
        admin_session.add_all(lessons)
        admin_session.commit()

        lesson_ids = [lesson.id for lesson in lessons]
        exam_lesson_id = lessons[-1].id

        learner_id = learner.id
        unit_id = unit.id
        active_course_id = active_course.id

    login_response = client.post(
        "/admin/login",
        data={"username": "admin2@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    page_response = client.get(f"/admin/unit-completion?user_id={learner_id}", follow_redirects=False)
    assert page_response.status_code == 200
    assert "Unit Completion" in page_response.text
    assert "learner2@example.com" in page_response.text

    set_response = client.post(
        "/admin/unit-completion",
        data={"user_id": learner_id, "unit_id": unit_id, "operation": "set_completed"},
        follow_redirects=False,
    )
    assert set_response.status_code == 303

    with admin_session_factory() as admin_session:
        enrollment = admin_session.scalar(
            select(UserCourseEnrollment).where(
                UserCourseEnrollment.user_id == learner_id,
                UserCourseEnrollment.course_version_id == active_course_id,
            )
        )
        assert enrollment is not None
        progress_rows = list(
            admin_session.scalars(
                select(UserLessonProgress).where(
                    UserLessonProgress.enrollment_id == enrollment.id,
                    UserLessonProgress.lesson_id.in_(lesson_ids),
                )
            )
        )
        assert {row.lesson_id for row in progress_rows} == set(lesson_ids)
        assert all(row.state == "completed" for row in progress_rows)
        if exam_lesson_id is not None:
            admin_session.add(
                ExamAttempt(
                    enrollment_id=enrollment.id,
                    lesson_id=exam_lesson_id,
                    attempt_no=1,
                )
            )
            admin_session.commit()

    unset_response = client.post(
        "/admin/unit-completion",
        data={"user_id": learner_id, "unit_id": unit_id, "operation": "unset_completed"},
        follow_redirects=False,
    )
    assert unset_response.status_code == 303

    with admin_session_factory() as admin_session:
        enrollment = admin_session.scalar(
            select(UserCourseEnrollment).where(
                UserCourseEnrollment.user_id == learner_id,
                UserCourseEnrollment.course_version_id == active_course_id,
            )
        )
        assert enrollment is not None
        progress_rows = list(
            admin_session.scalars(
                select(UserLessonProgress).where(
                    UserLessonProgress.enrollment_id == enrollment.id,
                    UserLessonProgress.lesson_id.in_(lesson_ids),
                )
            )
        )
        assert progress_rows == []
        exam_attempts = list(
            admin_session.scalars(
                select(ExamAttempt).where(
                    ExamAttempt.enrollment_id == enrollment.id,
                    ExamAttempt.lesson_id.in_(lesson_ids),
                )
            )
        )
        assert exam_attempts == []

    lesson_set_response = client.post(
        "/admin/unit-completion",
        data={"user_id": learner_id, "lesson_id": lesson_ids[0], "operation": "set_lesson_completed"},
        follow_redirects=False,
    )
    assert lesson_set_response.status_code == 303

    with admin_session_factory() as admin_session:
        enrollment = admin_session.scalar(
            select(UserCourseEnrollment).where(
                UserCourseEnrollment.user_id == learner_id,
                UserCourseEnrollment.course_version_id == active_course_id,
            )
        )
        assert enrollment is not None
        lesson_progress = admin_session.get(
            UserLessonProgress,
            {"enrollment_id": enrollment.id, "lesson_id": lesson_ids[0]},
        )
        assert lesson_progress is not None
        assert lesson_progress.state == "completed"
        admin_session.add(
            ExamAttempt(
                enrollment_id=enrollment.id,
                lesson_id=lesson_ids[0],
                attempt_no=1,
            )
        )
        admin_session.commit()

    lesson_unset_response = client.post(
        "/admin/unit-completion",
        data={"user_id": learner_id, "lesson_id": lesson_ids[0], "operation": "unset_lesson_completed"},
        follow_redirects=False,
    )
    assert lesson_unset_response.status_code == 303

    with admin_session_factory() as admin_session:
        enrollment = admin_session.scalar(
            select(UserCourseEnrollment).where(
                UserCourseEnrollment.user_id == learner_id,
                UserCourseEnrollment.course_version_id == active_course_id,
            )
        )
        assert enrollment is not None
        lesson_progress = admin_session.get(
            UserLessonProgress,
            {"enrollment_id": enrollment.id, "lesson_id": lesson_ids[0]},
        )
        assert lesson_progress is None
        lesson_attempts = list(
            admin_session.scalars(
                select(ExamAttempt).where(
                    ExamAttempt.enrollment_id == enrollment.id,
                    ExamAttempt.lesson_id == lesson_ids[0],
                )
            )
        )
        assert lesson_attempts == []

    with admin_session_factory() as admin_session:
        cleanup_course = admin_session.get(CourseVersion, active_course_id)
        cleanup_learner = admin_session.get(User, learner_id)
        cleanup_admin = admin_session.scalar(select(User).where(User.email == "admin2@example.com").limit(1))
        if cleanup_course is not None:
            admin_session.delete(cleanup_course)
        if cleanup_learner is not None:
            admin_session.delete(cleanup_learner)
        if cleanup_admin is not None:
            admin_session.delete(cleanup_admin)
        admin_session.commit()


def test_sqladmin_can_wipe_all_sentence_audio(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    bind = db_session.get_bind()
    admin_bind = bind.engine if isinstance(bind, Connection) else bind
    admin_session_factory = sessionmaker(
        bind=admin_bind,
        autoflush=False,
        autocommit=False,
        future=True,
    )

    with admin_session_factory() as admin_session:
        admin = User(
            email="admin-audio@example.com",
            password_hash=hash_password("password123"),
            is_admin=True,
        )
        course = CourseVersion(
            code="audio-admin-test",
            version=1,
            build_version=1,
            status="draft",
            config_version="test",
            config_hash="test-hash",
        )
        admin_session.add(course)
        admin_session.flush()
        sentence = Sentence(
            course_version_id=course.id,
            ja_text="これはテストです。",
            en_text="This is a test.",
            target_word_id=None,
            target_pattern_id=None,
        )
        audio_dir = tmp_path / "sentence-audio-admin-test" / "elevenlabs" / "voice-1"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / "sample.mp3"
        audio_path.write_bytes(b"fake-mp3")
        admin_session.add_all([admin, sentence])
        admin_session.flush()
        admin_session.add(
            SentenceAudioAsset(
                sentence_id=sentence.id,
                provider="elevenlabs",
                voice_id="voice-1",
                model_id="model-1",
                language_code="ja",
                text_hash="hash-1",
                source_text="sample",
                storage_path=str(audio_path),
                mime_type="audio/mpeg",
                byte_size=8,
                status="ready",
            )
        )
        admin_session.commit()

    login_response = client.post(
        "/admin/login",
        data={"username": "admin-audio@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    page_response = client.get("/admin/sentence-audio", follow_redirects=False)
    assert page_response.status_code == 200
    assert "Stored assets" in page_response.text

    wipe_response = client.post(
        "/admin/sentence-audio",
        data={"operation": "wipe_all_audio"},
        follow_redirects=False,
    )
    assert wipe_response.status_code == 303
    assert "/admin/sentence-audio?message=" in wipe_response.headers["location"]

    with admin_session_factory() as admin_session:
        remaining_assets = admin_session.scalar(select(func.count()).select_from(SentenceAudioAsset))
        cleanup_admin = admin_session.scalar(select(User).where(User.email == "admin-audio@example.com").limit(1))
        cleanup_course = admin_session.scalar(select(CourseVersion).where(CourseVersion.code == "audio-admin-test").limit(1))
        assert remaining_assets == 0
        if cleanup_course is not None:
            admin_session.delete(cleanup_course)
        if cleanup_admin is not None:
            admin_session.delete(cleanup_admin)
        admin_session.commit()

    assert not audio_path.exists()


def test_sqladmin_can_wipe_all_word_audio(
    client: TestClient, db_session: Session, tmp_path: Path
) -> None:
    bind = db_session.get_bind()
    admin_bind = bind.engine if isinstance(bind, Connection) else bind
    admin_session_factory = sessionmaker(
        bind=admin_bind,
        autoflush=False,
        autocommit=False,
        future=True,
    )

    with admin_session_factory() as admin_session:
        admin = User(
            email="admin-word-audio@example.com",
            password_hash=hash_password("password123"),
            is_admin=True,
        )
        course = CourseVersion(
            code="word-audio-admin-test",
            version=1,
            build_version=1,
            status="draft",
            config_version="test",
            config_hash="test-hash",
        )
        admin_session.add(course)
        admin_session.flush()
        word = Word(
            course_version_id=course.id,
            intro_order=1,
            canonical_writing_ja="学校",
            reading_kana="がっこう",
            gloss_primary_en="school",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            is_safe_pool=False,
            is_bootstrap_seed=False,
            source_kind="manual",
        )
        audio_dir = tmp_path / "word-audio-admin-test" / "elevenlabs" / "voice-1"
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = audio_dir / "sample.mp3"
        audio_path.write_bytes(b"fake-mp3")
        admin_session.add_all([admin, word])
        admin_session.flush()
        admin_session.add(
            WordAudioAsset(
                word_id=word.id,
                provider="elevenlabs",
                voice_id="voice-1",
                model_id="model-1",
                language_code="ja",
                text_hash="hash-1",
                source_text="学校",
                storage_path=str(audio_path),
                mime_type="audio/mpeg",
                byte_size=8,
                status="ready",
            )
        )
        admin_session.commit()

    login_response = client.post(
        "/admin/login",
        data={"username": "admin-word-audio@example.com", "password": "password123"},
        follow_redirects=False,
    )
    assert login_response.status_code == 302

    page_response = client.get("/admin/word-audio", follow_redirects=False)
    assert page_response.status_code == 200
    assert "Stored assets" in page_response.text

    wipe_response = client.post(
        "/admin/word-audio",
        data={"operation": "wipe_all_audio"},
        follow_redirects=False,
    )
    assert wipe_response.status_code == 303
    assert "/admin/word-audio?message=" in wipe_response.headers["location"]

    with admin_session_factory() as admin_session:
        remaining_assets = admin_session.scalar(select(func.count()).select_from(WordAudioAsset))
        cleanup_admin = admin_session.scalar(select(User).where(User.email == "admin-word-audio@example.com").limit(1))
        cleanup_course = admin_session.scalar(select(CourseVersion).where(CourseVersion.code == "word-audio-admin-test").limit(1))
        assert remaining_assets == 0
        if cleanup_course is not None:
            admin_session.delete(cleanup_course)
        if cleanup_admin is not None:
            admin_session.delete(cleanup_admin)
        admin_session.commit()

    assert not audio_path.exists()


def test_login_endpoint_returns_bearer_token(client: TestClient) -> None:
    _register_and_get_token(client)
    response = client.post("/api/v1/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"  # noqa: S105  # OAuth bearer token type literal


def test_next_item_includes_word_audio_urls_for_japanese_prompt_tokens(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        audio_service,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"elevenlabs_voice_id": "voice-lesson-test", "elevenlabs_model_id": "model-lesson-test"},
        )(),
    )
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    sentence = db_session.scalar(
        select(Sentence)
        .join(ItemSentenceTiles, ItemSentenceTiles.sentence_id == Sentence.id)
        .join(Item, Item.id == ItemSentenceTiles.item_id)
        .where(Item.prompt_lang == "ja")
        .order_by(Item.order_index.asc())
        .limit(1)
    )
    assert sentence is not None
    linked_word = db_session.scalar(
        select(Word)
        .join(SentenceWordLink, SentenceWordLink.word_id == Word.id)
        .join(
            SentenceUnit,
            (SentenceUnit.sentence_id == SentenceWordLink.sentence_id)
            & (SentenceUnit.lang == "ja")
            & (
                (SentenceUnit.lemma == Word.canonical_writing_ja)
                | (SentenceUnit.lemma == Word.reading_kana)
                | (SentenceUnit.surface == Word.canonical_writing_ja)
            ),
        )
        .where(SentenceWordLink.sentence_id == sentence.id)
        .order_by(Word.intro_order.asc(), Word.canonical_writing_ja.asc())
        .limit(1)
    )
    assert linked_word is not None

    audio_dir = tmp_path / "lesson-word-audio" / "elevenlabs" / "voice-1"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / "sample.mp3"
    audio_path.write_bytes(b"fake-mp3")
    db_session.add(
        WordAudioAsset(
            word_id=linked_word.id,
            provider="elevenlabs",
            voice_id="voice-lesson-test",
            model_id="model-lesson-test",
            language_code="ja",
            text_hash="hash-lesson-word-audio",
            source_text=linked_word.canonical_writing_ja,
            storage_path=str(audio_path),
            mime_type="audio/mpeg",
            byte_size=8,
            status="ready",
        )
    )
    db_session.commit()

    lesson_id = db_session.scalar(
        select(Lesson.id)
        .join(Item, Item.lesson_id == Lesson.id)
        .join(ItemSentenceTiles, ItemSentenceTiles.item_id == Item.id)
        .where(ItemSentenceTiles.sentence_id == sentence.id, Item.prompt_lang == "ja")
        .order_by(Lesson.order_index.asc(), Item.order_index.asc())
        .limit(1)
    )
    assert lesson_id is not None
    lesson_item_count = int(db_session.scalar(select(func.count()).select_from(Item).where(Item.lesson_id == lesson_id)) or 0)
    assert lesson_item_count > 0

    sentence_item: dict[str, object] | None = None
    for cursor in range(lesson_item_count):
        response = client.get(
            f"/api/v1/lessons/{lesson_id}/next-item",
            headers=headers,
            params={"cursor": cursor},
        )
        assert response.status_code == 200
        payload = response.json()
        if (
            payload["item_type"] == "sentence_tiles"
            and payload["prompt_lang"] == "ja"
            and payload["sentence_id"] == sentence.id
        ):
            sentence_item = payload
            break

    assert sentence_item is not None
    sentence_ja_tokens = sentence_item["sentence_ja_tokens"]
    assert isinstance(sentence_ja_tokens, list)
    assert any(token["word_audio_url"] is not None for token in sentence_ja_tokens if isinstance(token, dict))


def test_partial_submit_does_not_complete_normal_lesson(client: TestClient) -> None:
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    path_response = client.get("/api/v1/path", headers=headers)
    assert path_response.status_code == 200
    lesson_id = path_response.json()["current_lesson_id"]
    assert lesson_id is not None

    next_item_response = client.get(f"/api/v1/lessons/{lesson_id}/next-item", headers=headers, params={"cursor": 0})
    assert next_item_response.status_code == 200
    next_item = next_item_response.json()

    submit_response = client.post(
        f"/api/v1/lessons/{lesson_id}/submit",
        headers=headers,
        json={"answers": [{"item_id": next_item["item_id"], "user_answer": next_item["answer_tiles"][0]}]},
    )
    assert submit_response.status_code == 200
    payload = submit_response.json()
    assert payload["total_items"] >= 1
    assert payload["progress_state"] == "in_progress"


def test_sentence_tiles_include_distractors_in_returned_word_bank(
    client: TestClient,
    db_session: Session,
) -> None:
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    lesson_id = db_session.scalar(
        select(Lesson.id)
        .join(Item, Item.lesson_id == Lesson.id)
        .where(Item.type == "sentence_tiles")
        .order_by(Lesson.order_index.asc())
    )
    assert lesson_id is not None
    lesson_item_count = int(db_session.scalar(select(func.count()).select_from(Item).where(Item.lesson_id == lesson_id)) or 0)
    assert lesson_item_count > 0

    sentence_item: dict[str, object] | None = None
    for cursor in range(lesson_item_count):
        next_item_response = client.get(
            f"/api/v1/lessons/{lesson_id}/next-item",
            headers=headers,
            params={"cursor": cursor},
        )
        assert next_item_response.status_code == 200
        candidate_item = next_item_response.json()
        if candidate_item["item_type"] == "sentence_tiles":
            sentence_item = candidate_item
            break

    assert sentence_item is not None
    sentence_id = sentence_item["sentence_id"]
    assert isinstance(sentence_id, str)

    answer_lang = sentence_item["answer_lang"]
    assert isinstance(answer_lang, str)

    tile_set_id = db_session.scalar(
        select(SentenceTileSet.id).where(
            SentenceTileSet.sentence_id == sentence_id,
            SentenceTileSet.answer_lang == answer_lang,
        )
    )
    assert tile_set_id is not None

    correct_tiles = list(
        db_session.scalars(
            select(SentenceTile.text)
            .where(SentenceTile.tile_set_id == tile_set_id)
            .order_by(SentenceTile.tile_index.asc())
        )
    )
    returned_tiles = sentence_item["answer_tiles"]
    assert isinstance(returned_tiles, list)
    assert len(returned_tiles) > len(correct_tiles)
    assert set(correct_tiles).issubset(set(returned_tiles))


def test_first_section_kana_display_rewrites_sentence_prompt_and_tokens(
    kana_client: TestClient,
    db_session: Session,
) -> None:
    token = _register_and_get_token(kana_client)
    headers = {"Authorization": f"Bearer {token}"}

    lesson_id = db_session.scalar(
        select(Lesson.id)
        .join(Item, Item.lesson_id == Lesson.id)
        .where(Item.type == "sentence_tiles")
        .order_by(Lesson.order_index.asc())
    )
    assert lesson_id is not None
    lesson_item_count = int(db_session.scalar(select(func.count()).select_from(Item).where(Item.lesson_id == lesson_id)) or 0)
    assert lesson_item_count > 0

    sentence_item: dict[str, object] | None = None
    for cursor in range(lesson_item_count):
        response = kana_client.get(
            f"/api/v1/lessons/{lesson_id}/next-item",
            headers=headers,
            params={"cursor": cursor},
        )
        assert response.status_code == 200
        payload = response.json()
        if payload["item_type"] == "sentence_tiles":
            sentence_item = payload
            break

    assert sentence_item is not None
    prompt_text = sentence_item["prompt_text"]
    assert isinstance(prompt_text, str)
    assert not extract_kanji_chars(prompt_text)
    sentence_ja_tokens = sentence_item["sentence_ja_tokens"]
    assert isinstance(sentence_ja_tokens, list)
    assert sentence_ja_tokens
    assert all(isinstance(token, dict) for token in sentence_ja_tokens)
    assert all(not extract_kanji_chars(str(token["surface"])) for token in sentence_ja_tokens)
    assert any(
        isinstance(token["hints"], list)
        and token["hints"]
        and extract_kanji_chars(str(token["hints"][-1]))
        for token in sentence_ja_tokens
    )


def test_append_alternate_script_hint_adds_kana_for_kanji_display() -> None:
    hints = append_alternate_script_hint(
        ["I"],
        displayed_surface="私",
        lemma="私",
        reading="わたし",
        use_kana=False,
    )
    assert hints[-1] == "わたし"


def test_kanji_kana_match_item_returns_kana_options(
    client: TestClient,
    db_session: Session,
) -> None:
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    lesson = db_session.scalar(select(Lesson).order_by(Lesson.order_index.asc()).limit(1))
    assert lesson is not None
    word = db_session.scalar(
        select(Word).where(Word.canonical_writing_ja != Word.reading_kana).order_by(Word.intro_order.asc()).limit(1)
    )
    assert word is not None
    next_order_index = (
        int(
            db_session.scalar(
                select(Item.order_index).where(Item.lesson_id == lesson.id).order_by(Item.order_index.desc()).limit(1)
            )
            or 0
        )
        + 1
    )
    item = Item(
        lesson_id=lesson.id,
        order_index=next_order_index,
        type="kanji_kana_match",
        prompt_lang="ja",
        answer_lang="ja",
    )
    db_session.add(item)
    db_session.flush()
    db_session.add(
        ItemKanjiKanaMatch(
            item_id=item.id,
            word_id=word.id,
            prompt_script="kanji",
            answer_script="kana",
        )
    )
    db_session.commit()

    lesson_item_count = int(db_session.scalar(select(func.count()).select_from(Item).where(Item.lesson_id == lesson.id)) or 0)
    assert lesson_item_count > 0

    payload: dict[str, object] | None = None
    for cursor in range(lesson_item_count):
        response = client.get(
            f"/api/v1/lessons/{lesson.id}/next-item",
            headers=headers,
            params={"cursor": cursor},
        )
        assert response.status_code == 200
        candidate_payload = response.json()
        if candidate_payload["item_type"] == "kanji_kana_match" and candidate_payload["prompt_text"] == word.canonical_writing_ja:
            payload = candidate_payload
            break

    assert payload is not None
    assert payload["item_type"] == "kanji_kana_match"
    assert payload["prompt_text"] == word.canonical_writing_ja
    assert word.reading_kana in cast(list[str], payload["answer_tiles"])


def test_next_item_shuffles_normal_lesson_without_breaking_intro_order(
    client: TestClient,
    db_session: Session,
) -> None:
    token = _register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    unit_id = db_session.scalar(select(Unit.id).order_by(Unit.order_index.asc()).limit(1))
    assert unit_id is not None
    lesson = Lesson(unit_id=unit_id, kind="normal", order_index=999, target_item_count=4)
    db_session.add(lesson)
    db_session.flush()

    sentence_id = db_session.scalar(select(Sentence.id).order_by(Sentence.id.asc()).limit(1))
    word_id = db_session.scalar(
        select(Word.id).where(Word.canonical_writing_ja != Word.reading_kana).order_by(Word.intro_order.asc()).limit(1)
    )
    assert sentence_id is not None
    assert word_id is not None
    ja_tile_set_id = db_session.scalar(
        select(SentenceTileSet.id).where(SentenceTileSet.sentence_id == sentence_id, SentenceTileSet.answer_lang == "ja")
    )
    en_tile_set_id = db_session.scalar(
        select(SentenceTileSet.id).where(SentenceTileSet.sentence_id == sentence_id, SentenceTileSet.answer_lang == "en")
    )
    assert ja_tile_set_id is not None
    assert en_tile_set_id is not None
    sentence_word_link = db_session.get(SentenceWordLink, {"sentence_id": sentence_id, "word_id": word_id})
    if sentence_word_link is None:
        db_session.add(SentenceWordLink(sentence_id=sentence_id, word_id=word_id, role="target"))

    en_ja_sentence_item = Item(
        lesson_id=lesson.id,
        order_index=1,
        type="sentence_tiles",
        prompt_lang="en",
        answer_lang="ja",
    )
    word_choice_item = Item(
        lesson_id=lesson.id,
        order_index=2,
        type="word_choice",
        prompt_lang="ja",
        answer_lang="en",
    )
    ja_en_sentence_item = Item(
        lesson_id=lesson.id,
        order_index=3,
        type="sentence_tiles",
        prompt_lang="ja",
        answer_lang="en",
    )
    kana_kanji_item = Item(
        lesson_id=lesson.id,
        order_index=4,
        type="kanji_kana_match",
        prompt_lang="ja",
        answer_lang="ja",
    )
    db_session.add_all([en_ja_sentence_item, word_choice_item, ja_en_sentence_item, kana_kanji_item])
    db_session.flush()
    db_session.add_all(
        [
            ItemSentenceTiles(
                item_id=en_ja_sentence_item.id,
                sentence_id=sentence_id,
                tile_set_id=ja_tile_set_id,
            ),
            ItemWordChoice(item_id=word_choice_item.id, word_id=word_id),
            ItemSentenceTiles(
                item_id=ja_en_sentence_item.id,
                sentence_id=sentence_id,
                tile_set_id=en_tile_set_id,
            ),
            ItemKanjiKanaMatch(
                item_id=kana_kanji_item.id,
                word_id=word_id,
                prompt_script="kana",
                answer_script="kanji",
            ),
        ]
    )
    db_session.commit()

    observed_item_types: list[tuple[str, str, str]] = []
    for cursor in range(4):
        response = client.get(
            f"/api/v1/lessons/{lesson.id}/next-item",
            headers=headers,
            params={"cursor": cursor},
        )
        assert response.status_code == 200
        payload = response.json()
        observed_item_types.append((payload["item_type"], payload["prompt_lang"], payload["answer_lang"]))

    assert observed_item_types == [
        ("kanji_kana_match", "ja", "ja"),
        ("word_choice", "ja", "en"),
        ("sentence_tiles", "ja", "en"),
        ("sentence_tiles", "en", "ja"),
    ]
