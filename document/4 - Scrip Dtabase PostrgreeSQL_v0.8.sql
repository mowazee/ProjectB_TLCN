-- =====================================================================
-- DATABASE SCHEMA - MVP + P2, phiên bản 0.8 (18/10/2026)
-- Sinh tự động từ Alembic (0001_core → 0108), KHÔNG sửa tay.
-- Đồng bộ: "0 - Đặc tả SDD v0.8" mục 6 và
--          "3 - Các lược đồ usecase_sequence_erd_database v0.8" (ERD, 17 bảng)
-- Tạo lại (trong backend/, PowerShell):
--   $env:DATABASE_URL="postgresql+psycopg://u:p@localhost/db"
--   .venv\Scripts\alembic.exe upgrade head --sql > "..\document\4 - Scrip Dtabase PostrgreeSQL_v0.8.sql"
--   (rồi chép lại khối chú thích này lên đầu file)
-- Thay đổi so với bản v0.5 (bản đó chỉ có phần MVP, revision 0001):
--   + 5 bảng P2: document_approvals (0101), notifications (0102),
--     document_extracted_fields (0103), storage_locations + borrow_requests (0104)
--   + documents.storage_location_id (0104); processing_jobs.kind thêm
--     EXTRACT, CLASSIFY, BULK_IMPORT (0105); notifications.message, link_url (0106)
--   + processing_jobs.document_id cho phép NULL (job cấp lô BULK_IMPORT)
--   + trigger audit append-only cho phép ON DELETE SET NULL khi purge (FR-07)
-- v0.7: thêm vai trò VIEWER - Người dùng thông thường (0107, chỉ dữ liệu, không đổi bảng).
-- v0.8: chia sẻ tài liệu đã xuất bản (FR-13, D-09, 0108): documents.share_mode
--   (private | internal | public, mặc định internal) và bảng document_shares (17 bảng).
-- Toàn bộ chạy trong một transaction (BEGIN … COMMIT).
-- =====================================================================
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE departments (
    id SERIAL NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE roles (
    id SERIAL NOT NULL, 
    name VARCHAR(50) NOT NULL, 
    description VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE TABLE categories (
    id SERIAL NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    parent_id INTEGER, 
    retention_period_years INTEGER, 
    description TEXT, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code), 
    FOREIGN KEY(parent_id) REFERENCES categories (id) ON DELETE CASCADE
);

CREATE TABLE users (
    id UUID NOT NULL, 
    department_id INTEGER, 
    username VARCHAR(50) NOT NULL, 
    email VARCHAR(100) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    full_name VARCHAR(100) NOT NULL, 
    phone VARCHAR(20), 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    last_login_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
    UNIQUE (username), 
    UNIQUE (email)
);

CREATE INDEX ix_users_department_id ON users (department_id);

CREATE TABLE user_roles (
    user_id UUID NOT NULL, 
    role_id INTEGER NOT NULL, 
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (user_id, role_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE
);

CREATE TABLE documents (
    id UUID NOT NULL, 
    category_id INTEGER NOT NULL, 
    owner_id UUID, 
    department_id INTEGER, 
    title VARCHAR(255) NOT NULL, 
    document_code VARCHAR(100), 
    file_name VARCHAR(255) NOT NULL, 
    storage_key VARCHAR(500) NOT NULL, 
    mime_type VARCHAR(100) NOT NULL, 
    bytes BIGINT NOT NULL, 
    lifecycle_status VARCHAR(30) DEFAULT 'active' NOT NULL, 
    approval_status VARCHAR(30) DEFAULT 'draft' NOT NULL, 
    is_handwritten BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT, 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
    CONSTRAINT ck_documents_lifecycle_status CHECK (lifecycle_status IN ('active', 'deleted')), 
    CONSTRAINT ck_documents_approval_status CHECK (approval_status IN ('draft', 'pending_review', 'approved', 'rejected', 'published', 'unpublished'))
);

CREATE INDEX ix_documents_lifecycle_status ON documents (lifecycle_status);

CREATE INDEX ix_documents_category_id ON documents (category_id);

CREATE INDEX ix_documents_owner_id ON documents (owner_id);

CREATE INDEX ix_documents_department_id ON documents (department_id);

CREATE INDEX ix_documents_created_at ON documents (created_at);

CREATE TABLE document_pages (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    page_number INTEGER NOT NULL, 
    image_key VARCHAR(500) NOT NULL, 
    width INTEGER NOT NULL, 
    height INTEGER NOT NULL, 
    ocr_status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_document_page UNIQUE (document_id, page_number), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    CONSTRAINT ck_document_pages_ocr_status CHECK (ocr_status IN ('pending', 'completed', 'failed', 'needs_review'))
);

CREATE INDEX ix_document_pages_document_id ON document_pages (document_id);

CREATE TABLE processing_jobs (
    id UUID NOT NULL, 
    document_id UUID, 
    page_id UUID, 
    kind VARCHAR(30) NOT NULL, 
    queue_name VARCHAR(50) DEFAULT 'default' NOT NULL, 
    status VARCHAR(30) DEFAULT 'queued' NOT NULL, 
    schema_version INTEGER DEFAULT '1' NOT NULL, 
    idempotency_key VARCHAR(200) NOT NULL, 
    progress INTEGER DEFAULT '0' NOT NULL, 
    priority INTEGER DEFAULT '0' NOT NULL, 
    attempt INTEGER DEFAULT '0' NOT NULL, 
    max_attempts INTEGER DEFAULT '3' NOT NULL, 
    worker_id VARCHAR(100), 
    payload JSONB, 
    result JSONB, 
    error_code VARCHAR(50), 
    error_detail TEXT, 
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT chk_job_attempt CHECK (attempt <= max_attempts), 
    CONSTRAINT chk_job_progress CHECK (progress BETWEEN 0 AND 100), 
    CONSTRAINT ck_jobs_kind CHECK (kind IN ('OCR')), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(page_id) REFERENCES document_pages (id) ON DELETE CASCADE, 
    CONSTRAINT ck_jobs_status CHECK (status IN ('queued', 'processing', 'completed', 'failed')), 
    UNIQUE (idempotency_key)
);

CREATE INDEX ix_processing_jobs_document_id ON processing_jobs (document_id);

CREATE INDEX idx_jobs_kind_status ON processing_jobs (kind, status);

CREATE TABLE ocr_results (
    id UUID NOT NULL, 
    page_id UUID NOT NULL, 
    job_id UUID, 
    raw_text TEXT NOT NULL, 
    boxes JSONB, 
    confidence NUMERIC(5, 2), 
    engine_version VARCHAR(50) NOT NULL, 
    search_vector TSVECTOR, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_ocr_results_page_job UNIQUE (page_id, job_id), 
    FOREIGN KEY(page_id) REFERENCES document_pages (id) ON DELETE CASCADE, 
    FOREIGN KEY(job_id) REFERENCES processing_jobs (id) ON DELETE SET NULL
);

CREATE INDEX ix_ocr_results_page_id ON ocr_results (page_id);

CREATE INDEX idx_ocr_results_search_vector ON ocr_results USING gin (search_vector);

CREATE TABLE ocr_corrections (
    id UUID NOT NULL, 
    page_id UUID NOT NULL, 
    edited_by UUID, 
    version INTEGER NOT NULL, 
    corrected_text TEXT NOT NULL, 
    base_version INTEGER NOT NULL, 
    edited_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_ocr_corrections_page_version UNIQUE (page_id, version), 
    FOREIGN KEY(page_id) REFERENCES document_pages (id) ON DELETE CASCADE, 
    FOREIGN KEY(edited_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_ocr_corrections_page_id ON ocr_corrections (page_id);

CREATE TABLE audit_logs (
    id BIGSERIAL NOT NULL, 
    user_id UUID, 
    document_id UUID, 
    action VARCHAR(100) NOT NULL, 
    module VARCHAR(50) NOT NULL, 
    entity_type VARCHAR(50), 
    entity_id VARCHAR(100), 
    result VARCHAR(30) NOT NULL, 
    ip_address VARCHAR(45), 
    user_agent TEXT, 
    request_id VARCHAR(64), 
    state_before JSONB, 
    state_after JSONB, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    CONSTRAINT ck_audit_logs_result CHECK (result IN ('success', 'failure'))
);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE INDEX ix_audit_logs_document_id ON audit_logs (document_id);

CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at);

CREATE OR REPLACE FUNCTION fn_audit_logs_append_only() RETURNS trigger AS $$
BEGIN
    -- Cho phép duy nhất UPDATE do khóa ngoại ON DELETE SET NULL (purge tài liệu, FR-07):
    -- chỉ user_id/document_id đổi sang NULL, mọi cột khác giữ nguyên.
    IF TG_OP = 'UPDATE'
       AND (NEW.user_id IS NULL OR NEW.user_id IS NOT DISTINCT FROM OLD.user_id)
       AND (NEW.document_id IS NULL OR NEW.document_id IS NOT DISTINCT FROM OLD.document_id)
       AND (to_jsonb(NEW) - 'user_id' - 'document_id') = (to_jsonb(OLD) - 'user_id' - 'document_id')
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_logs chỉ cho phép thêm mới (append-only)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_append_only
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION fn_audit_logs_append_only();;

INSERT INTO roles (name, description) VALUES ('ADMIN', 'Quản trị viên hệ thống');

INSERT INTO roles (name, description) VALUES ('OFFICER', 'Nhân viên nghiệp vụ');

INSERT INTO roles (name, description) VALUES ('APPROVER', 'Kiểm duyệt viên');

INSERT INTO departments (name, code, description) VALUES ('Phòng Hành chính - Tổng hợp', 'HC-TH', 'Đơn vị mặc định');

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0101

CREATE TABLE document_approvals (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    approver_id UUID, 
    action VARCHAR(20) NOT NULL, 
    comments TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_document_approvals_action CHECK (action IN ('submit', 'approve', 'reject', 'publish', 'unpublish')), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(approver_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_document_approvals_document_id ON document_approvals (document_id);

UPDATE alembic_version SET version_num='0101' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0101 -> 0102

CREATE TABLE notifications (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    type VARCHAR(50) NOT NULL, 
    is_read BOOLEAN DEFAULT false NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notifications_user_read ON notifications (user_id, is_read);

UPDATE alembic_version SET version_num='0102' WHERE alembic_version.version_num = '0101';

-- Running upgrade 0102 -> 0103

CREATE TABLE document_extracted_fields (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    field_name VARCHAR(100) NOT NULL, 
    field_value TEXT, 
    extracted_method VARCHAR(30) NOT NULL, 
    is_verified BOOLEAN DEFAULT false NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_extracted_fields_document_field UNIQUE (document_id, field_name), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
);

CREATE INDEX ix_document_extracted_fields_document_id ON document_extracted_fields (document_id);

UPDATE alembic_version SET version_num='0103' WHERE alembic_version.version_num = '0102';

-- Running upgrade 0103 -> 0104

CREATE TABLE storage_locations (
    id SERIAL NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE borrow_requests (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    requester_id UUID, 
    approver_id UUID, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    from_date DATE NOT NULL, 
    to_date DATE NOT NULL, 
    purpose TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_borrow_requests_status CHECK (status IN ('pending', 'approved', 'rejected', 'returned')), 
    CONSTRAINT ck_borrow_requests_dates CHECK (from_date <= to_date), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(requester_id) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(approver_id) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_borrow_requests_requester_id ON borrow_requests (requester_id);

CREATE INDEX ix_borrow_requests_document_status ON borrow_requests (document_id, status);

ALTER TABLE documents ADD COLUMN storage_location_id INTEGER;

ALTER TABLE documents ADD CONSTRAINT fk_documents_storage_location_id FOREIGN KEY(storage_location_id) REFERENCES storage_locations (id) ON DELETE SET NULL;

CREATE INDEX ix_documents_storage_location_id ON documents (storage_location_id);

UPDATE alembic_version SET version_num='0104' WHERE alembic_version.version_num = '0103';

-- Running upgrade 0104 -> 0105

ALTER TABLE processing_jobs DROP CONSTRAINT ck_jobs_kind;

ALTER TABLE processing_jobs ADD CONSTRAINT ck_jobs_kind CHECK (kind IN ('OCR', 'EXTRACT', 'CLASSIFY', 'BULK_IMPORT'));

UPDATE alembic_version SET version_num='0105' WHERE alembic_version.version_num = '0104';

-- Running upgrade 0105 -> 0106

ALTER TABLE notifications ADD COLUMN message TEXT;

ALTER TABLE notifications ADD COLUMN link_url VARCHAR(500);

UPDATE alembic_version SET version_num='0106' WHERE alembic_version.version_num = '0105';

-- Running upgrade 0106 -> 0107

INSERT INTO roles (name, description) SELECT 'VIEWER', 'Người dùng thông thường' WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'VIEWER');

UPDATE alembic_version SET version_num='0107' WHERE alembic_version.version_num = '0106';

-- Running upgrade 0107 -> 0108

ALTER TABLE documents ADD COLUMN share_mode VARCHAR(30) DEFAULT 'internal' NOT NULL;

ALTER TABLE documents ADD CONSTRAINT ck_documents_share_mode CHECK (share_mode IN ('private', 'internal', 'public'));

CREATE TABLE document_shares (
    id BIGSERIAL NOT NULL, 
    document_id UUID NOT NULL, 
    department_id INTEGER, 
    user_id UUID, 
    created_by UUID, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_document_shares_target CHECK ((department_id IS NULL) <> (user_id IS NULL)), 
    CONSTRAINT uq_document_shares_department UNIQUE (document_id, department_id), 
    CONSTRAINT uq_document_shares_user UNIQUE (document_id, user_id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_document_shares_document_id ON document_shares (document_id);

CREATE INDEX ix_document_shares_department_id ON document_shares (department_id);

CREATE INDEX ix_document_shares_user_id ON document_shares (user_id);

UPDATE alembic_version SET version_num='0108' WHERE alembic_version.version_num = '0107';

COMMIT;

