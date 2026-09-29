/* Запустить, если возникли траблы с кириллицей */
USE MaxBotDispecherTasks;
GO

-- Что сейчас в БД (для проверки)
SELECT name, definition
FROM sys.check_constraints
WHERE parent_object_id = OBJECT_ID(N'dbo.Schedule_Rule');
GO

IF EXISTS (SELECT 1 FROM sys.check_constraints
           WHERE name = N'CK_Schedule_Rule_WeekdayMask'
             AND parent_object_id = OBJECT_ID(N'dbo.Schedule_Rule'))
    ALTER TABLE dbo.Schedule_Rule DROP CONSTRAINT CK_Schedule_Rule_WeekdayMask;
GO

ALTER TABLE dbo.Schedule_Rule
    ADD CONSTRAINT CK_Schedule_Rule_WeekdayMask
    CHECK (WeekdayMask BETWEEN 0 AND 127);
GO

-- Проверка результата
SELECT name, definition
FROM sys.check_constraints
WHERE parent_object_id = OBJECT_ID(N'dbo.Schedule_Rule');
GO
