# Từ điển dữ liệu

Sinh tự động bằng `backend/scripts/gen_data_dictionary.py` từ model SQLAlchemy (khớp migration Alembic, kiểm tra bằng `alembic check` trong CI). Ý nghĩa nghiệp vụ của từng bảng: file 3 mục IV (bảng mô tả thực thể); quy tắc nghiệp vụ: [BUSINESS_RULES.md](BUSINESS_RULES.md).

Tổng số bảng: **22**.

| Bảng | Module | Số cột |
|---|---|---|
| [`audit_logs`](#audit-logs) | audit | 14 |
| [`borrow_requests`](#borrow-requests) | borrowing | 9 |
| [`categories`](#categories) | categories | 8 |
| [`daily_activity_stats`](#daily-activity-stats) | analytics | 5 |
| [`departments`](#departments) | users | 5 |
| [`document_approvals`](#document-approvals) | workflow | 6 |
| [`document_attachments`](#document-attachments) | documents | 8 |
| [`document_extracted_fields`](#document-extracted-fields) | extraction | 6 |
| [`document_pages`](#document-pages) | documents | 7 |
| [`document_shares`](#document-shares) | documents | 6 |
| [`documents`](#documents) | documents | 25 |
| [`guide_documents`](#guide-documents) | guides | 10 |
| [`notifications`](#notifications) | notifications | 8 |
| [`ocr_corrections`](#ocr-corrections) | ocr | 7 |
| [`ocr_results`](#ocr-results) | ocr | 9 |
| [`processing_jobs`](#processing-jobs) | jobs | 20 |
| [`roles`](#roles) | users | 4 |
| [`share_links`](#share-links) | sharing | 12 |
| [`storage_locations`](#storage-locations) | borrowing | 4 |
| [`system_settings`](#system-settings) | settings | 4 |
| [`user_roles`](#user-roles) | users | 3 |
| [`users`](#users) | users | 11 |

## audit_logs

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | BIGINT | không | PK |  |
| `user_id` | UUID | có | → users.id ON DELETE SET NULL |  |
| `document_id` | UUID | có | → documents.id ON DELETE SET NULL |  |
| `action` | VARCHAR(100) | không |  |  |
| `module` | VARCHAR(50) | không |  |  |
| `entity_type` | VARCHAR(50) | có |  |  |
| `entity_id` | VARCHAR(100) | có |  |  |
| `result` | VARCHAR(30) ∈ {success, failure} | không |  | success |
| `ip_address` | VARCHAR(45) | có |  |  |
| `user_agent` | TEXT | có |  |  |
| `request_id` | VARCHAR(64) | có |  |  |
| `state_before` | JSONB | có |  |  |
| `state_after` | JSONB | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `idx_audit_logs_action_created_at`: (action, created_at)
- Index `idx_audit_logs_created_at`: (created_at)
- Index `ix_audit_logs_document_id`: (document_id)
- Index `ix_audit_logs_user_id`: (user_id)

## borrow_requests

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `requester_id` | UUID | có | → users.id ON DELETE SET NULL |  |
| `approver_id` | UUID | có | → users.id ON DELETE SET NULL |  |
| `status` | VARCHAR(20) | không |  | pending |
| `from_date` | DATE | không |  |  |
| `to_date` | DATE | không |  |  |
| `purpose` | TEXT | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_borrow_requests_document_status`: (document_id, status)
- Index `ix_borrow_requests_requester_id`: (requester_id)

## categories

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | INTEGER | không | PK |  |
| `name` | VARCHAR(150) | không |  |  |
| `code` | VARCHAR(50) | không | UNIQUE |  |
| `parent_id` | INTEGER | có | → categories.id ON DELETE CASCADE |  |
| `retention_period_years` | INTEGER | có |  |  |
| `description` | TEXT | có |  |  |
| `is_active` | BOOLEAN | không |  | true |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

## daily_activity_stats

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `day` | DATE | không | PK |  |
| `user_id` | UUID | không | PK, → users.id ON DELETE CASCADE |  |
| `metric` | VARCHAR(50) | không | PK |  |
| `department_id` | INTEGER | có | → departments.id ON DELETE SET NULL |  |
| `value` | FLOAT | không |  | 0 |

- Index `ix_daily_activity_stats_department_id`: (department_id)

## departments

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | INTEGER | không | PK |  |
| `name` | VARCHAR(150) | không |  |  |
| `code` | VARCHAR(50) | không | UNIQUE |  |
| `description` | TEXT | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

## document_approvals

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `approver_id` | UUID | có | → users.id ON DELETE SET NULL |  |
| `action` | VARCHAR(20) | không |  |  |
| `comments` | TEXT | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_document_approvals_document_id`: (document_id)

## document_attachments

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `file_name` | VARCHAR(255) | không |  |  |
| `storage_key` | VARCHAR(500) | không |  |  |
| `mime_type` | VARCHAR(100) | không |  |  |
| `bytes` | BIGINT | không |  |  |
| `uploaded_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_document_attachments_document_id`: (document_id)

## document_extracted_fields

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `field_name` | VARCHAR(100) | không |  |  |
| `field_value` | TEXT | có |  |  |
| `extracted_method` | VARCHAR(30) | không |  |  |
| `is_verified` | BOOLEAN | không |  | false |

- Index `ix_document_extracted_fields_document_id`: (document_id)
- UNIQUE `uq_extracted_fields_document_field`: (document_id, field_name)

## document_pages

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `page_number` | INTEGER | không |  |  |
| `image_key` | VARCHAR(500) | không |  |  |
| `width` | INTEGER | không |  |  |
| `height` | INTEGER | không |  |  |
| `ocr_status` | VARCHAR(30) ∈ {pending, completed, failed, needs_review} | không |  | pending |

- Index `ix_document_pages_document_id`: (document_id)
- UNIQUE `uq_document_page`: (document_id, page_number)

## document_shares

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | BIGINT | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `department_id` | INTEGER | có | → departments.id ON DELETE CASCADE |  |
| `user_id` | UUID | có | → users.id ON DELETE CASCADE |  |
| `created_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_document_shares_department_id`: (department_id)
- Index `ix_document_shares_document_id`: (document_id)
- Index `ix_document_shares_user_id`: (user_id)
- UNIQUE `uq_document_shares_user`: (document_id, user_id)
- UNIQUE `uq_document_shares_department`: (document_id, department_id)

## documents

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `category_id` | INTEGER | không | → categories.id ON DELETE RESTRICT |  |
| `owner_id` | UUID | có | → users.id ON DELETE SET NULL |  |
| `department_id` | INTEGER | có | → departments.id ON DELETE SET NULL |  |
| `title` | VARCHAR(255) | không |  |  |
| `document_code` | VARCHAR(100) | có |  |  |
| `file_name` | VARCHAR(255) | không |  |  |
| `storage_key` | VARCHAR(500) | không |  |  |
| `mime_type` | VARCHAR(100) | không |  |  |
| `bytes` | BIGINT | không |  |  |
| `lifecycle_status` | VARCHAR(30) ∈ {active, deleted} | không |  | active |
| `approval_status` | VARCHAR(30) ∈ {draft, pending_review, approved, rejected, published, unpublished} | không |  | draft |
| `is_handwritten` | BOOLEAN | không |  | false |
| `category_source` | VARCHAR(30) ∈ {user, auto, pending} | không |  | user |
| `share_mode` | VARCHAR(30) ∈ {private, internal, public} | không |  | internal |
| `validity_status` | VARCHAR(30) ∈ {unspecified, effective, effective_until, expired} | không |  | unspecified |
| `valid_until` | DATE | có |  |  |
| `validity_updated_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `validity_updated_at` | TIMESTAMP WITH TIME ZONE | có |  |  |
| `validity_reminded_on` | DATE | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |
| `updated_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |
| `deleted_at` | TIMESTAMP WITH TIME ZONE | có |  |  |
| `storage_location_id` | INTEGER | có | → storage_locations.id ON DELETE SET NULL |  |
| `has_physical_copy` | BOOLEAN | có |  |  |

- Index `ix_documents_category_id`: (category_id)
- Index `ix_documents_created_at`: (created_at)
- Index `ix_documents_department_id`: (department_id)
- Index `ix_documents_lifecycle_status`: (lifecycle_status)
- Index `ix_documents_owner_id`: (owner_id)
- Index `ix_documents_storage_location_id`: (storage_location_id)
- Index `ix_documents_validity`: (validity_status, valid_until)

## guide_documents

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `title` | VARCHAR(255) | không |  |  |
| `description` | TEXT | có |  |  |
| `file_name` | VARCHAR(255) | không |  |  |
| `storage_key` | VARCHAR(500) | không |  |  |
| `mime_type` | VARCHAR(150) | không |  |  |
| `bytes` | BIGINT | không |  |  |
| `uploaded_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |
| `updated_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_guide_documents_created_at`: (created_at)

## notifications

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `user_id` | UUID | không | → users.id ON DELETE CASCADE |  |
| `title` | VARCHAR(255) | không |  |  |
| `message` | TEXT | có |  |  |
| `type` | VARCHAR(50) | không |  |  |
| `link_url` | VARCHAR(500) | có |  |  |
| `is_read` | BOOLEAN | không |  | false |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_notifications_user_read`: (user_id, is_read)

## ocr_corrections

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `page_id` | UUID | không | → document_pages.id ON DELETE CASCADE |  |
| `edited_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `version` | INTEGER | không |  |  |
| `corrected_text` | TEXT | không |  |  |
| `base_version` | INTEGER | không |  |  |
| `edited_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_ocr_corrections_page_id`: (page_id)
- UNIQUE `uq_ocr_corrections_page_version`: (page_id, version)

## ocr_results

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `page_id` | UUID | không | → document_pages.id ON DELETE CASCADE |  |
| `job_id` | UUID | có | → processing_jobs.id ON DELETE SET NULL |  |
| `raw_text` | TEXT | không |  |  |
| `boxes` | JSONB | có |  |  |
| `confidence` | NUMERIC(5, 2) | có |  |  |
| `engine_version` | VARCHAR(50) | không |  |  |
| `search_vector` | TSVECTOR | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `idx_ocr_results_search_vector`: (search_vector)
- Index `ix_ocr_results_page_id`: (page_id)
- UNIQUE `uq_ocr_results_page_job`: (page_id, job_id)

## processing_jobs

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | có | → documents.id ON DELETE CASCADE |  |
| `page_id` | UUID | có | → document_pages.id ON DELETE CASCADE |  |
| `kind` | VARCHAR(30) | không |  |  |
| `queue_name` | VARCHAR(50) | không |  | default |
| `status` | VARCHAR(30) ∈ {queued, processing, completed, failed} | không |  | queued |
| `schema_version` | INTEGER | không |  | 1 |
| `idempotency_key` | VARCHAR(200) | không | UNIQUE |  |
| `progress` | INTEGER | không |  | 0 |
| `priority` | INTEGER | không |  | 0 |
| `attempt` | INTEGER | không |  | 0 |
| `max_attempts` | INTEGER | không |  | 3 |
| `worker_id` | VARCHAR(100) | có |  |  |
| `payload` | JSONB | có |  |  |
| `result` | JSONB | có |  |  |
| `error_code` | VARCHAR(50) | có |  |  |
| `error_detail` | TEXT | có |  |  |
| `queued_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |
| `started_at` | TIMESTAMP WITH TIME ZONE | có |  |  |
| `finished_at` | TIMESTAMP WITH TIME ZONE | có |  |  |

- Index `idx_jobs_kind_status`: (kind, status)
- Index `ix_processing_jobs_document_id`: (document_id)

## roles

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | INTEGER | không | PK |  |
| `name` | VARCHAR(50) | không | UNIQUE |  |
| `description` | VARCHAR(255) | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

## share_links

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `document_id` | UUID | không | → documents.id ON DELETE CASCADE |  |
| `token_hash` | VARCHAR(64) | không | UNIQUE |  |
| `recipient_email` | VARCHAR(255) | không |  |  |
| `allow_download` | BOOLEAN | không |  | False |
| `expires_at` | TIMESTAMP WITH TIME ZONE | không |  |  |
| `revoked_at` | TIMESTAMP WITH TIME ZONE | có |  |  |
| `email_status` | VARCHAR(20) | không |  | pending |
| `created_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |
| `last_accessed_at` | TIMESTAMP WITH TIME ZONE | có |  |  |
| `access_count` | INTEGER | không |  | 0 |

- Index `ix_share_links_document_id`: (document_id)

## storage_locations

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | INTEGER | không | PK |  |
| `name` | VARCHAR(150) | không |  |  |
| `code` | VARCHAR(50) | không | UNIQUE |  |
| `is_virtual` | BOOLEAN | không |  | false |

## system_settings

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `key` | VARCHAR(100) | không | PK |  |
| `value` | JSONB | không |  |  |
| `updated_by` | UUID | có | → users.id ON DELETE SET NULL |  |
| `updated_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

## user_roles

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `user_id` | UUID | không | PK, → users.id ON DELETE CASCADE |  |
| `role_id` | INTEGER | không | PK, → roles.id ON DELETE CASCADE |  |
| `assigned_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

## users

| Cột | Kiểu | Null | Khóa / tham chiếu | Mặc định |
|---|---|---|---|---|
| `id` | UUID | không | PK |  |
| `department_id` | INTEGER | có | → departments.id ON DELETE SET NULL |  |
| `username` | VARCHAR(50) | không | UNIQUE |  |
| `email` | VARCHAR(100) | không | UNIQUE |  |
| `password_hash` | VARCHAR(255) | không |  |  |
| `full_name` | VARCHAR(100) | không |  |  |
| `phone` | VARCHAR(20) | có |  |  |
| `is_active` | BOOLEAN | không |  | true |
| `last_login_at` | TIMESTAMP WITH TIME ZONE | có |  |  |
| `created_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |
| `updated_at` | TIMESTAMP WITH TIME ZONE | không |  | now() |

- Index `ix_users_department_id`: (department_id)
