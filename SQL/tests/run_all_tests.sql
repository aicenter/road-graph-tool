-- function to run all tests within road-graph-tool
CREATE OR REPLACE FUNCTION run_all_tests() RETURNS SETOF TEXT AS $$
    DECLARE
        record RECORD;
        tmp TEXT;
BEGIN
    -- temp table to store results
    CREATE TEMP TABLE test_results (
        test_name TEXT,
        passed BOOLEAN
    );
    -- run tests
    RAISE NOTICE 'Running all tests...';

    FOR record IN EXECUTE run_all_tests_helper()
    LOOP
        DECLARE
            record_content TEXT := regexp_replace(record::TEXT, '^[(]["](.*)["][)]$', '\1');
        BEGIN
        -- store results
        IF record_content ~ '^ok \d+' THEN
            -- This is a passing test (starts with 'ok ' followed by a number)
            INSERT INTO test_results (test_name, passed) VALUES (tmp, TRUE);
        ELSIF record_content ~ '^not ok \d+' THEN
            -- This is a failing test (starts with 'not ok ' followed by a number)
            INSERT INTO test_results (test_name, passed) VALUES (tmp, FALSE);
        ELSIF record_content LIKE '# Subtest: %' THEN
            -- This is the start of a new test
            tmp := substring(record_content FROM '# Subtest: (.*)');
        END IF;
        -- return results
        RETURN NEXT record;
        END;
    END LOOP;

    -- return results
    RETURN NEXT 'Summary:';
    FOR record IN
        SELECT * FROM test_results
    LOOP
        -- build up the test result string
        IF record.passed THEN
            tmp := 'ok';
        ELSE
            tmp := 'not ok';
        END IF;
        tmp := tmp || ' ' || record.test_name;
        RETURN NEXT tmp;
    END LOOP;
    -- calculate sum of passed and failed tests
    FOR record in
        SELECT COUNT(*) AS total, SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS passed, SUM(CASE WHEN passed THEN 0 ELSE 1 END) AS failed FROM test_results
    LOOP
        RETURN NEXT '1..' || record.total;
        RETURN NEXT 'Passed: ' || record.passed;
        RETURN NEXT 'Failed: ' || record.failed;
    END LOOP;
    -- drop temp table
    DROP TABLE test_results;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION run_all_tests_helper() RETURNS TEXT AS $$
DECLARE
    result text := '';
    func text;
    func_names text[] := findfuncs('^run_all_.*_tests$');
    func_names_clean text[];
BEGIN
    FOREACH func IN ARRAY func_names
        LOOP
            func_names_clean := array_append(func_names_clean, split_part(func, '.', 2));
        END LOOP;
    FOREACH func IN ARRAY func_names_clean
        LOOP
            -- Append to the result
            result := result || '        SELECT * FROM ' || func || '()';

            -- Add UNION ALL except for the last item
            -- debug print
            IF func != func_names_clean[array_upper(func_names, 1)] THEN
                result := result || E'\n        UNION ALL\n';
            END IF;
        END LOOP;

    RETURN result;
END;
$$ LANGUAGE plpgsql;
