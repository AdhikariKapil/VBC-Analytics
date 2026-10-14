DROP TABLE IF EXISTS admission_chaos;
CREATE TABLE admission_chaos LIKE admissions;
INSERT INTO admission_chaos SELECT * FROM admissions;
