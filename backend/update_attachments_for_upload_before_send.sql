USE `cooking_agent`;

SET @has_attachment_kind := (
  SELECT COUNT(*)
  FROM `INFORMATION_SCHEMA`.`COLUMNS`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` = 'attachments'
    AND `COLUMN_NAME` = 'attachment_kind'
);

SET @sql := IF(
  @has_attachment_kind = 0,
  "ALTER TABLE `attachments` ADD COLUMN `attachment_kind` VARCHAR(32) NOT NULL DEFAULT 'document' COMMENT '附件类型：document/image' AFTER `file_size`",
  "SELECT 'skip add attachment_kind' AS message"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @message_id_nullable := (
  SELECT `IS_NULLABLE`
  FROM `INFORMATION_SCHEMA`.`COLUMNS`
  WHERE `TABLE_SCHEMA` = DATABASE()
    AND `TABLE_NAME` = 'attachments'
    AND `COLUMN_NAME` = 'message_id'
  LIMIT 1
);

SET @sql := IF(
  @message_id_nullable = 'NO',
  "ALTER TABLE `attachments` MODIFY COLUMN `message_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '绑定消息ID，上传成功后可为空，发送消息成功后再绑定'",
  "SELECT 'skip modify message_id' AS message"
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

UPDATE `attachments`
SET `attachment_kind` = CASE
  WHEN LOWER(`file_ext`) IN ('.jpg', '.jpeg', '.png', '.webp') THEN 'image'
  ELSE 'document'
END;
