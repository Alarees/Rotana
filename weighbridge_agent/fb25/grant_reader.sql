/*
  Creates the read-only Firebird user used by the agent. Works on Firebird 2.5 and 3.0.

  Run ONCE as SYSDBA from the Firebird folder (Windows CMD), then delete the password from your history:
    isql -user SYSDBA -password <sysdba-password> localhost/3052:SMARTBRIDGE -i grant_reader.sql

  1) Change the password below BEFORE running.
  2) To change the user later: ALTER USER SB_READER PASSWORD 'new';  then update config.ini.
*/
CREATE USER SB_READER PASSWORD 'ChangeMe_2026';
GRANT SELECT ON TBLWEIGHTS TO SB_READER;
GRANT SELECT ON TBLTRUCKS TO SB_READER;
GRANT SELECT ON TBLDRIVERS TO SB_READER;
GRANT SELECT ON TBLCOMPANIES TO SB_READER;
GRANT SELECT ON TBLCUSTOMFIELD1 TO SB_READER;
COMMIT;
