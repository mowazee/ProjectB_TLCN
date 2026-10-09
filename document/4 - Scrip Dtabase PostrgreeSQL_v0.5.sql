-- =====================================================================
-- DATABASE SCHEMA - MVP, baseline v2 (sinh tự động từ Alembic, KHÔNG sửa tay)
-- Đồng bộ: "0 - Đặc tả Spec Driven Development v0.2" mục 6 và
--          "3 - Các lượt đồ usercase_squence_erd_database v2" (ERD)
-- Tạo lại:  alembic upgrade head --sql > docs/schema_mvp_v2.sql
-- Thay thế "4 - Database scrip (PostgreSQL).sql" (bản 25/09, trước khi chuẩn hóa).
-- Bảng P2 (storage_locations, document_approvals, borrow_requests,
-- document_extracted_fields, notifications) sẽ có ở migration P2.
-- =====================================================================
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE categories (
    id SERIAL NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    parent_id INTEGER, 
    retention_period_years INTEGER, 
    description TEXT, 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(parent_id) REFERENCES categories (id) ON DELETE CASCADE, 
    UNIQUE (code)
);

CREATE TABLE departments (
    id SERIAL NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    code VARCHAR(50) NOT NULL, 
    description TEXT, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE TABLE roles (
    id SERIAL NOT NULL, 
    name VARCHAR(50) NOT NULL, 
    description VARCHAR(255), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
    UNIQUE (email), 
    UNIQUE (username)
);

CREATE INDEX ix_users_department_id ON users (department_id);

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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(category_id) REFERENCES categories (id) ON DELETE RESTRICT, 
    FOREIGN KEY(department_id) REFERENCES departments (id) ON DELETE SET NULL, 
    FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT ck_documents_lifecycle_status CHECK (lifecycle_status IN ('active', 'deleted')), 
    CONSTRAINT ck_documents_approval_status CHECK (approval_status IN ('draft', 'pending_review', 'approved', 'rejected', 'published', 'unpublished'))
);

CREATE INDEX ix_documents_category_id ON documents (category_id);

CREATE INDEX ix_documents_created_at ON documents (created_at);

CREATE INDEX ix_documents_department_id ON documents (department_id);

CREATE INDEX ix_documents_lifecycle_status ON documents (lifecycle_status);

CREATE INDEX ix_documents_owner_id ON documents (owner_id);

CREATE TABLE user_roles (
    user_id UUID NOT NULL, 
    role_id INTEGER NOT NULL, 
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (user_id, role_id), 
    FOREIGN KEY(role_id) REFERENCES roles (id) ON DELETE CASCADE, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL, 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL, 
    CONSTRAINT ck_audit_logs_result CHECK (result IN ('success', 'failure'))
);

CREATE INDEX idx_audit_logs_created_at ON audit_logs (created_at);

CREATE INDEX ix_audit_logs_document_id ON audit_logs (document_id);

CREATE INDEX ix_audit_logs_user_id ON audit_logs (user_id);

CREATE TABLE document_pages (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    page_number INTEGER NOT NULL, 
    image_key VARCHAR(500) NOT NULL, 
    width INTEGER NOT NULL, 
    height INTEGER NOT NULL, 
    ocr_status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    CONSTRAINT uq_document_page UNIQUE (document_id, page_number), 
    CONSTRAINT ck_document_pages_ocr_status CHECK (ocr_status IN ('pending', 'completed', 'failed', 'needs_review'))
);

CREATE INDEX ix_document_pages_document_id ON document_pages (document_id);

CREATE TABLE ocr_corrections (
    id UUID NOT NULL, 
    page_id UUID NOT NULL, 
    edited_by UUID, 
    version INTEGER NOT NULL, 
    corrected_text TEXT NOT NULL, 
    base_version INTEGER NOT NULL, 
    edited_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(edited_by) REFERENCES users (id) ON DELETE SET NULL, 
    FOREIGN KEY(page_id) REFERENCES document_pages (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ocr_corrections_page_version UNIQUE (page_id, version)
);

CREATE INDEX ix_ocr_corrections_page_id ON ocr_corrections (page_id);

CREATE TABLE processing_jobs (
    id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    page_id UUID, 
    kind VARCHAR(30) NOT NULL, 
    queue_name VARCHAR(50) DEFAULT 'ocr' NOT NULL, 
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
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT chk_job_attempt CHECK (attempt <= max_attempts), 
    CONSTRAINT chk_job_progress CHECK (progress BETWEEN 0 AND 100), 
    FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE, 
    FOREIGN KEY(page_id) REFERENCES document_pages (id) ON DELETE CASCADE, 
    UNIQUE (idempotency_key), 
    CONSTRAINT ck_jobs_kind CHECK (kind IN ('OCR')), 
    CONSTRAINT ck_jobs_status CHECK (status IN ('queued', 'processing', 'completed', 'failed'))
);

CREATE INDEX idx_jobs_kind_status ON processing_jobs (kind, status);

CREATE INDEX ix_processing_jobs_document_id ON processing_jobs (document_id);

CREATE TABLE ocr_results (
    id UUID NOT NULL, 
    page_id UUID NOT NULL, 
    job_id UUID, 
    raw_text TEXT NOT NULL, 
    boxes JSONB, 
    confidence NUMERIC(5, 2), 
    engine_version VARCHAR(50) NOT NULL, 
    search_vector TSVECTOR, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(job_id) REFERENCES processing_jobs (id) ON DELETE SET NULL, 
    FOREIGN KEY(page_id) REFERENCES document_pages (id) ON DELETE CASCADE, 
    CONSTRAINT uq_ocr_results_page_job UNIQUE (page_id, job_id)
);

CREATE INDEX idx_ocr_results_search_vector ON ocr_results USING gin (search_vector);

CREATE INDEX ix_ocr_results_page_id ON ocr_results (page_id);

CREATE OR REPLACE FUNCTION fn_audit_logs_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs chỉ cho phép thêm mới (append-only)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_append_only
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION fn_audit_logs_append_only();;

INSERT INTO roles (name, description) VALUES ('ADMIN', 'Quản trị viên hệ thống');

INSERT INTO roles (name, description) VALUES ('OFFICER', 'Nhân viên nghiệp vụ');

INSERT INTO roles (name, description) VALUES ('APPROVER', 'Kiểm duyệt viên');

INSERT INTO departments (name, code, description) VALUES ('Phòng Hành chính - Tổng hợp', 'HC-TH', 'Đơn vị mặc định khi khởi tạo hệ thống');

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

