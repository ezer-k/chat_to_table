-- Fetch the latest main branch and redeploy WorldTable without dropping saved datasets.
USE ROLE ACCOUNTADMIN;

ALTER GIT REPOSITORY WORLDTABLE.APP.SOURCE FETCH;

EXECUTE IMMEDIATE FROM
  @WORLDTABLE.APP.SOURCE/branches/main/sql/install.sql;
