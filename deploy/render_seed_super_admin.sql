-- Render PostgreSQL seed for Vortex Forge.
-- Run this only after Django migrations have created the tables.
--
-- Purpose:
-- - ensure the only super admin account is pippozago08@gmail.com
-- - create the account if it does not exist
-- - update the account if it already exists
--
-- Important:
-- this file contains only the Django password hash, not the plain password.

BEGIN;

-- Avoid a username conflict before the upsert below.
UPDATE accounts_user
SET username = 'user_' || id
WHERE lower(username) = 'pippozago08'
  AND lower(email) <> 'pippozago08@gmail.com';

-- Keep this email as the only super admin.
UPDATE accounts_user
SET
    role = 'user',
    is_superuser = FALSE,
    is_staff = FALSE,
    can_manage_builds = FALSE,
    can_manage_users = FALSE,
    can_manage_bans = FALSE,
    can_view_contacts = FALSE,
    can_manage_settings = FALSE
WHERE lower(email) <> 'pippozago08@gmail.com'
  AND (
      role = 'super_admin'
      OR is_superuser = TRUE
      OR can_manage_settings = TRUE
  );

INSERT INTO accounts_user (
    password,
    last_login,
    is_superuser,
    username,
    first_name,
    last_name,
    is_staff,
    is_active,
    date_joined,
    email,
    avatar,
    phone,
    role,
    is_email_verified,
    can_manage_builds,
    can_manage_users,
    can_manage_bans,
    can_view_contacts,
    can_manage_settings
)
VALUES (
    'pbkdf2_sha256$1000000$u8xeJ3kuvt5fqftRPk1z6m$n3P41aBlcW2m0L017Q9veOgH7nSHe5D9nnBnQKHecXE=',
    NULL,
    TRUE,
    'pippozago08',
    'Pippo',
    'Zago',
    TRUE,
    TRUE,
    NOW(),
    'pippozago08@gmail.com',
    '',
    '',
    'super_admin',
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE,
    TRUE
)
ON CONFLICT (email) DO UPDATE
SET
    password = EXCLUDED.password,
    username = EXCLUDED.username,
    first_name = EXCLUDED.first_name,
    last_name = EXCLUDED.last_name,
    is_superuser = TRUE,
    is_staff = TRUE,
    is_active = TRUE,
    role = 'super_admin',
    is_email_verified = TRUE,
    can_manage_builds = TRUE,
    can_manage_users = TRUE,
    can_manage_bans = TRUE,
    can_view_contacts = TRUE,
    can_manage_settings = TRUE;

COMMIT;
