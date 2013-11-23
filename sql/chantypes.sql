-- devices attached to the modbusRTU or modbusTCP network accessible to droid controller
BEGIN TRANSACTION; 
CREATE TABLE 'chantypes'(num integer,type integer,name,descr); -- ebables using mixed rtu and tcp inputs
INSERT INTO 'chantypes' VALUES(1,2,'AI','analogue inputs');
INSERT INTO 'chantypes' VALUES(2,3,'1W','1wire temperature sensors');
INSERT INTO 'chantypes' VALUES(3,1,'DI','binary inputs'); 
INSERT INTO 'chantypes' VALUES(4,0,'DO','binary outputs');
INSERT INTO 'chantypes' VALUES(0,4,'','counters'); -- not visible as type, use for di subtype only - WHAT?

-- INSERT INTO 'chantypes' VALUES(5,0,'DO','counters on binary inputs'); 

CREATE UNIQUE INDEX num_chantypes on 'chantypes'(num); -- chantype ordering numbers must be unique
CREATE UNIQUE INDEX type_chantypes on 'chantypes'(type); -- chantype types must be unique
CREATE UNIQUE INDEX name_chantypes on 'chantypes'(name); -- chantype names must be unique

COMMIT;
    