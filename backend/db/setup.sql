-- M1-0 bootstrap: schema + least-privilege application user.
--
-- Do not run this file directly with a real password in it. Use db/setup.sh,
-- which reads the password from backend/.env and substitutes the placeholder
-- below. That keeps the credential out of git (Constitution §2.5).
--
-- Safe to re-run: every statement is idempotent.

CREATE DATABASE IF NOT EXISTS rbac_learning
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

CREATE DATABASE IF NOT EXISTS rbac_learning_test
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Create the user for both socket-style ('localhost') and TCP ('127.0.0.1')
-- connections. The app connects over TCP, so the 127.0.0.1 entry is the one
-- that matters; 'localhost' keeps the mysql CLI usable for debugging.
CREATE USER IF NOT EXISTS 'rbac_app'@'localhost' IDENTIFIED BY '__RBAC_APP_PASSWORD__';
ALTER USER 'rbac_app'@'localhost' IDENTIFIED BY '__RBAC_APP_PASSWORD__';

CREATE USER IF NOT EXISTS 'rbac_app'@'127.0.0.1' IDENTIFIED BY '__RBAC_APP_PASSWORD__';
ALTER USER 'rbac_app'@'127.0.0.1' IDENTIFIED BY '__RBAC_APP_PASSWORD__';

-- Least privilege: DML plus the DDL needed by create_all (M1 schema mechanism).
-- Deliberately no GRANT OPTION, FILE, SUPER, or global privileges.
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON rbac_learning.* TO 'rbac_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON rbac_learning_test.* TO 'rbac_app'@'localhost';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON rbac_learning.* TO 'rbac_app'@'127.0.0.1';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER, REFERENCES
  ON rbac_learning_test.* TO 'rbac_app'@'127.0.0.1';

FLUSH PRIVILEGES;
