-- Every row returns (rule_name, failure_count)

-- All checks target the admission table by default. To run against another table, replace FROM admisson with FROM admission_chaos before executing.


SELECT 'age_out_of_range' AS rule, COUNT(*) AS failures
FROM admissions WHERE age < 0 OR age > 150

UNION ALL
SELECT 'invalid_gender', COUNT(*)
FROM admissions WHERE gender NOT IN ('Male', 'Female')

UNION ALL
SELECT 'discharge_before_admission', COUNT(*)
FROM admissions WHERE discharge_date < date_of_admission

UNION ALL
SELECT 'negative_room_number', COUNT(*)
FROM admissions WHERE room_number < 0

UNION ALL
SELECT 'future_admission_date', COUNT(*)
FROM admissions WHERE date_of_admission > CURDATE()

UNION ALL
select 'null_in_required_column', COUNT(*)
FROM admissions WHERE
age IS NUll OR
gender IS NUll OR
blood_type IS NUll OR
medical_condition IS NUll OR
date_of_admission IS NUll OR
doctor IS NUll OR
hospital IS NUll OR
insurance_provider IS NUll OR
admission_type IS NUll OR
medication IS NUll OR
room_number IS NULL

UNION ALL
SELECT 'los_inconsistent', COUNT(*)
FROM admissions
WHERE length_of_stay <> DATEDIFF(discharge_date, date_of_admission)

UNION ALL
SELECT 'negative_billing', COUNT(*)
FROM admissions
WHERE billing_amount < 0;
