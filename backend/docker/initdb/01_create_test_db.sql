-- 테스트용 DB (명세 11.9, 16절 Docker 줄). postgres 이미지가 처음 뜰 때 POSTGRES_USER로 한 번 실행한다.
-- pytest는 TEST_DATABASE_URL의 DB를 지웠다가 다시 만들므로 개발용 DB(creamoff)와 따로 둔다.
-- 소유자는 이 파일을 실행하는 POSTGRES_USER(creamoff)다. 인코딩은 11.1대로 UTF8.
CREATE DATABASE creamoff_test TEMPLATE template0 ENCODING 'UTF8';
