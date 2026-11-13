DROP TABLE IF EXISTS admissions_chaos;
CREATE TABLE admissions_chaos LIKE admissions;
INSERT INTO admissions_chaos SELECT * FROM admissions;
