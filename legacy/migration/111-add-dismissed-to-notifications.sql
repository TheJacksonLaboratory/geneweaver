ALTER TABLE production.notifications
    ADD COLUMN dismissed boolean NOT NULL default FALSE;