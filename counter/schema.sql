-- 방문자 카운터 (개인정보 없음: IP 저장 안 함, sid 는 브라우저 탭마다 만드는 임의 문자열)
CREATE TABLE IF NOT EXISTS presence (sid TEXT PRIMARY KEY, ts INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS presence_ts ON presence (ts);
CREATE TABLE IF NOT EXISTS pageviews (day TEXT NOT NULL, path TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, path));
