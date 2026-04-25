# 智能做菜助手 Agent MySQL 建表文档

## 1. 说明

本文档给出当前项目的 MySQL 建库建表 SQL，可直接用于本地开发环境初始化数据库。

设计原则：

- 数据库：MySQL 8.0+，优先 MySQL 8.4 LTS
- 存储引擎：InnoDB
- 字符集：utf8mb4
- 排序规则：utf8mb4_0900_ai_ci
- 主键：`BIGINT UNSIGNED AUTO_INCREMENT`
- 对外业务 ID：`public_id`，便于前后端和日志使用
- 长文本：`LONGTEXT`
- 结构化结果：`JSON`

本版本包含以下核心表：

- `users`
- `conversations`
- `messages`
- `attachments`
- `parse_results`
- `agent_runs`

## 2. 建库 SQL

```sql
CREATE DATABASE IF NOT EXISTS `cooking_agent_db`
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `cooking_agent_db`;
```

## 3. 建表 SQL

### 3.1 用户表 `users`

```sql
CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `public_id` VARCHAR(64) NOT NULL COMMENT '对外业务ID，例如 user_xxx',
  `username` VARCHAR(100) NOT NULL COMMENT '用户名/昵称',
  `email` VARCHAR(191) NOT NULL COMMENT '登录邮箱',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
  `status` VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '用户状态',
  `last_login_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近登录时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_public_id` (`public_id`),
  UNIQUE KEY `uk_users_email` (`email`),
  KEY `idx_users_status` (`status`),
  KEY `idx_users_created_at` (`created_at`)
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
COMMENT='用户表';
```

### 3.2 会话表 `conversations`

```sql
CREATE TABLE IF NOT EXISTS `conversations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `public_id` VARCHAR(64) NOT NULL COMMENT '对外业务ID，例如 conv_xxx',
  `user_id` BIGINT UNSIGNED NOT NULL COMMENT '所属用户ID',
  `title` VARCHAR(255) NOT NULL DEFAULT '新对话' COMMENT '会话标题',
  `status` VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '会话状态',
  `latest_message_at` DATETIME(3) NULL DEFAULT NULL COMMENT '最近消息时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_conversations_public_id` (`public_id`),
  KEY `idx_conversations_user_created` (`user_id`, `created_at`),
  KEY `idx_conversations_user_latest` (`user_id`, `latest_message_at`),
  KEY `idx_conversations_status` (`status`),
  CONSTRAINT `fk_conversations_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
COMMENT='会话表';
```

### 3.3 消息表 `messages`

```sql
CREATE TABLE IF NOT EXISTS `messages` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `public_id` VARCHAR(64) NOT NULL COMMENT '对外业务ID，例如 msg_xxx',
  `conversation_id` BIGINT UNSIGNED NOT NULL COMMENT '所属会话ID',
  `user_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '发送者用户ID，assistant/system消息可为空',
  `role` VARCHAR(32) NOT NULL COMMENT '角色：user/assistant/system/tool',
  `message_type` VARCHAR(32) NOT NULL DEFAULT 'text' COMMENT '消息类型：text/image/file/mixed',
  `content` LONGTEXT NOT NULL COMMENT '消息正文',
  `status` VARCHAR(32) NOT NULL DEFAULT 'completed' COMMENT '消息状态',
  `extra_metadata` JSON NULL COMMENT '扩展元数据',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_messages_public_id` (`public_id`),
  KEY `idx_messages_conversation_created` (`conversation_id`, `created_at`),
  KEY `idx_messages_user_id` (`user_id`),
  KEY `idx_messages_role` (`role`),
  KEY `idx_messages_type` (`message_type`),
  CONSTRAINT `fk_messages_conversation_id`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_messages_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE SET NULL
    ON UPDATE RESTRICT
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
COMMENT='消息表';
```

### 3.4 附件表 `attachments`

```sql
CREATE TABLE IF NOT EXISTS `attachments` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `public_id` VARCHAR(64) NOT NULL COMMENT '对外业务ID，例如 file_xxx',
  `conversation_id` BIGINT UNSIGNED NOT NULL COMMENT '所属会话ID',
  `message_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '绑定消息ID，上传成功后可为空，发送消息成功后再绑定',
  `original_name` VARCHAR(255) NOT NULL COMMENT '原始文件名',
  `stored_name` VARCHAR(255) NOT NULL COMMENT '存储文件名',
  `file_ext` VARCHAR(20) NOT NULL COMMENT '文件扩展名',
  `mime_type` VARCHAR(100) NOT NULL COMMENT 'MIME类型',
  `file_size` BIGINT UNSIGNED NOT NULL COMMENT '文件大小，单位字节',
  `attachment_kind` VARCHAR(32) NOT NULL DEFAULT 'document' COMMENT '附件类型：document/image',
  `storage_provider` VARCHAR(32) NOT NULL DEFAULT 'local' COMMENT '存储提供方',
  `storage_path` VARCHAR(1024) NOT NULL COMMENT '存储路径',
  `file_hash` VARCHAR(128) NULL DEFAULT NULL COMMENT '文件哈希',
  `parse_status` VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '解析状态',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_attachments_public_id` (`public_id`),
  KEY `idx_attachments_conversation_id` (`conversation_id`),
  KEY `idx_attachments_message_id` (`message_id`),
  KEY `idx_attachments_parse_status` (`parse_status`),
  KEY `idx_attachments_file_hash` (`file_hash`),
  CONSTRAINT `fk_attachments_conversation_id`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_attachments_message_id`
    FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
COMMENT='附件表';
```

### 3.5 解析结果表 `parse_results`

```sql
CREATE TABLE IF NOT EXISTS `parse_results` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部主键',
  `attachment_id` BIGINT UNSIGNED NOT NULL COMMENT '附件ID',
  `parser_name` VARCHAR(100) NOT NULL COMMENT '解析器名称',
  `parse_status` VARCHAR(32) NOT NULL DEFAULT 'completed' COMMENT '解析状态',
  `raw_text` LONGTEXT NULL COMMENT '抽取出的原始全文',
  `structured_result` JSON NULL COMMENT '结构化解析结果',
  `ocr_result` JSON NULL COMMENT 'OCR结构化结果',
  `embedding_status` VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '向量化状态',
  `started_at` DATETIME(3) NULL DEFAULT NULL COMMENT '解析开始时间',
  `completed_at` DATETIME(3) NULL DEFAULT NULL COMMENT '解析完成时间',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '创建时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_parse_results_attachment_id` (`attachment_id`),
  KEY `idx_parse_results_status` (`parse_status`),
  KEY `idx_parse_results_embedding_status` (`embedding_status`),
  CONSTRAINT `fk_parse_results_attachment_id`
    FOREIGN KEY (`attachment_id`) REFERENCES `attachments` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
COMMENT='附件解析结果表';
```

### 3.6 Agent 运行记录表 `agent_runs`

```sql
CREATE TABLE IF NOT EXISTS `agent_runs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '内部自增主键，仅用于数据库关联与排序，不直接暴露给前端',
  `public_id` VARCHAR(64) NOT NULL COMMENT '对外业务ID，建议格式 run_xxx，便于接口返回、日志追踪和排障',
  `conversation_id` BIGINT UNSIGNED NOT NULL COMMENT '所属会话ID，表示本次 Agent 运行归属于哪一个会话上下文',
  `message_id` BIGINT UNSIGNED NOT NULL COMMENT '触发本次运行的消息ID，通常是用户最新提交的一条消息',
  `user_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '关联用户ID；系统触发、匿名请求或历史补偿任务时允许为空',
  `intent_type` VARCHAR(64) NOT NULL COMMENT '意图类型，例如 recipe_generation、document_qa、image_qa、ingredient_analysis',
  `workflow_name` VARCHAR(100) NOT NULL COMMENT '实际执行的工作流名称，例如 recipe_workflow、file_qa_workflow、multimodal_workflow',
  `run_status` VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '运行状态，建议值 pending、running、completed、failed、cancelled',
  `model_name` VARCHAR(100) NULL DEFAULT NULL COMMENT '本次运行使用的模型或服务名称，例如 gpt-4o-mini、gpt-5、ocr-service-v1',
  `input_snapshot` JSON NULL COMMENT '输入快照，保存执行时的标准化输入，如用户文本、附件ID、识别参数、上下文摘要',
  `output_snapshot` JSON NULL COMMENT '输出快照，保存执行结果，如最终回复、结构化菜谱、抽取字段、参考来源',
  `error_code` VARCHAR(64) NULL DEFAULT NULL COMMENT '错误码，供程序判断失败类型，例如 MODEL_TIMEOUT、PARSER_FAILED、OCR_EMPTY',
  `error_message` TEXT NULL COMMENT '错误详情，记录报错原因、异常摘要或下游服务返回信息，便于排查问题',
  `started_at` DATETIME(3) NULL DEFAULT NULL COMMENT '开始执行时间，进入 running 状态时写入',
  `completed_at` DATETIME(3) NULL DEFAULT NULL COMMENT '执行完成时间，成功、失败或取消时写入',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) COMMENT '记录创建时间，即本条运行记录首次落库时间',
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3) COMMENT '记录更新时间，每次状态变更或快照更新时自动刷新',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_runs_public_id` (`public_id`),
  KEY `idx_agent_runs_conversation_created` (`conversation_id`, `created_at`),
  KEY `idx_agent_runs_message_id` (`message_id`),
  KEY `idx_agent_runs_user_id` (`user_id`),
  KEY `idx_agent_runs_status` (`run_status`),
  KEY `idx_agent_runs_intent_type` (`intent_type`),
  CONSTRAINT `fk_agent_runs_conversation_id`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_agent_runs_message_id`
    FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_agent_runs_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE SET NULL
    ON UPDATE RESTRICT
) ENGINE=InnoDB
DEFAULT CHARSET=utf8mb4
COLLATE=utf8mb4_0900_ai_ci
COMMENT='Agent运行记录表';
```

字段说明补充：

- `intent_type` 用来表示“系统识别出的用户需求类别”，它决定后续应该走哪个 Agent 路由。
- `workflow_name` 用来表示“后端实际执行的处理链路”，同一种意图也可能映射到不同工作流版本。
- `run_status` 建议统一收敛为有限状态集合，避免后续统计和前端展示时出现同义词混用。
- `input_snapshot` 建议存标准化后的输入，而不是原始请求全量拷贝，重点保留文本、附件、参数和上下文摘要。
- `output_snapshot` 建议存业务上真正需要复盘的结果，例如菜谱标题、步骤、食材清单、答案文本、引用片段。
- `error_code` 给程序和监控系统用，`error_message` 给开发排查用，两者最好同时保留。
- `idx_agent_runs_conversation_created` 主要用于按会话查看运行历史，支持“某个会话下最近一次 Agent 执行”的查询。
- `ON DELETE CASCADE` 说明会话或消息被删除时，其运行记录也一并删除；`user_id` 用 `SET NULL` 是为了保留历史运行日志。

## 4. 初始化顺序

建议按下面顺序执行：

1. 创建数据库 `cooking_agent`
2. 创建 `users`
3. 创建 `conversations`
4. 创建 `messages`
5. 创建 `attachments`
6. 创建 `parse_results`
7. 创建 `agent_runs`

原因：

- 外键依赖顺序清晰
- 避免因为依赖表未创建而报错

## 5. 可直接执行的完整 SQL

如果你要一次性执行，可以直接使用下面这份完整 SQL。

```sql
CREATE DATABASE IF NOT EXISTS `cooking_agent`
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE `cooking_agent`;

CREATE TABLE IF NOT EXISTS `users` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `public_id` VARCHAR(64) NOT NULL,
  `username` VARCHAR(100) NOT NULL,
  `email` VARCHAR(191) NOT NULL,
  `password_hash` VARCHAR(255) NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'active',
  `last_login_at` DATETIME(3) NULL DEFAULT NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_users_public_id` (`public_id`),
  UNIQUE KEY `uk_users_email` (`email`),
  KEY `idx_users_status` (`status`),
  KEY `idx_users_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `conversations` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `public_id` VARCHAR(64) NOT NULL,
  `user_id` BIGINT UNSIGNED NOT NULL,
  `title` VARCHAR(255) NOT NULL DEFAULT '新对话',
  `status` VARCHAR(32) NOT NULL DEFAULT 'active',
  `latest_message_at` DATETIME(3) NULL DEFAULT NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_conversations_public_id` (`public_id`),
  KEY `idx_conversations_user_created` (`user_id`, `created_at`),
  KEY `idx_conversations_user_latest` (`user_id`, `latest_message_at`),
  KEY `idx_conversations_status` (`status`),
  CONSTRAINT `fk_conversations_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `messages` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `public_id` VARCHAR(64) NOT NULL,
  `conversation_id` BIGINT UNSIGNED NOT NULL,
  `user_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `role` VARCHAR(32) NOT NULL,
  `message_type` VARCHAR(32) NOT NULL DEFAULT 'text',
  `content` LONGTEXT NOT NULL,
  `status` VARCHAR(32) NOT NULL DEFAULT 'completed',
  `extra_metadata` JSON NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_messages_public_id` (`public_id`),
  KEY `idx_messages_conversation_created` (`conversation_id`, `created_at`),
  KEY `idx_messages_user_id` (`user_id`),
  KEY `idx_messages_role` (`role`),
  KEY `idx_messages_type` (`message_type`),
  CONSTRAINT `fk_messages_conversation_id`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_messages_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE SET NULL
    ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `attachments` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `public_id` VARCHAR(64) NOT NULL,
  `conversation_id` BIGINT UNSIGNED NOT NULL,
  `message_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `original_name` VARCHAR(255) NOT NULL,
  `stored_name` VARCHAR(255) NOT NULL,
  `file_ext` VARCHAR(20) NOT NULL,
  `mime_type` VARCHAR(100) NOT NULL,
  `file_size` BIGINT UNSIGNED NOT NULL,
  `attachment_kind` VARCHAR(32) NOT NULL DEFAULT 'document',
  `storage_provider` VARCHAR(32) NOT NULL DEFAULT 'local',
  `storage_path` VARCHAR(1024) NOT NULL,
  `file_hash` VARCHAR(128) NULL DEFAULT NULL,
  `parse_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_attachments_public_id` (`public_id`),
  KEY `idx_attachments_conversation_id` (`conversation_id`),
  KEY `idx_attachments_message_id` (`message_id`),
  KEY `idx_attachments_parse_status` (`parse_status`),
  KEY `idx_attachments_file_hash` (`file_hash`),
  CONSTRAINT `fk_attachments_conversation_id`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_attachments_message_id`
    FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `parse_results` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `attachment_id` BIGINT UNSIGNED NOT NULL,
  `parser_name` VARCHAR(100) NOT NULL,
  `parse_status` VARCHAR(32) NOT NULL DEFAULT 'completed',
  `raw_text` LONGTEXT NULL,
  `structured_result` JSON NULL,
  `ocr_result` JSON NULL,
  `embedding_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `started_at` DATETIME(3) NULL DEFAULT NULL,
  `completed_at` DATETIME(3) NULL DEFAULT NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_parse_results_attachment_id` (`attachment_id`),
  KEY `idx_parse_results_status` (`parse_status`),
  KEY `idx_parse_results_embedding_status` (`embedding_status`),
  CONSTRAINT `fk_parse_results_attachment_id`
    FOREIGN KEY (`attachment_id`) REFERENCES `attachments` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS `agent_runs` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `public_id` VARCHAR(64) NOT NULL,
  `conversation_id` BIGINT UNSIGNED NOT NULL,
  `message_id` BIGINT UNSIGNED NOT NULL,
  `user_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `intent_type` VARCHAR(64) NOT NULL,
  `workflow_name` VARCHAR(100) NOT NULL,
  `run_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
  `model_name` VARCHAR(100) NULL DEFAULT NULL,
  `input_snapshot` JSON NULL,
  `output_snapshot` JSON NULL,
  `error_code` VARCHAR(64) NULL DEFAULT NULL,
  `error_message` TEXT NULL,
  `started_at` DATETIME(3) NULL DEFAULT NULL,
  `completed_at` DATETIME(3) NULL DEFAULT NULL,
  `created_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  `updated_at` DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_agent_runs_public_id` (`public_id`),
  KEY `idx_agent_runs_conversation_created` (`conversation_id`, `created_at`),
  KEY `idx_agent_runs_message_id` (`message_id`),
  KEY `idx_agent_runs_user_id` (`user_id`),
  KEY `idx_agent_runs_status` (`run_status`),
  KEY `idx_agent_runs_intent_type` (`intent_type`),
  CONSTRAINT `fk_agent_runs_conversation_id`
    FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_agent_runs_message_id`
    FOREIGN KEY (`message_id`) REFERENCES `messages` (`id`)
    ON DELETE CASCADE
    ON UPDATE RESTRICT,
  CONSTRAINT `fk_agent_runs_user_id`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
    ON DELETE SET NULL
    ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

## 6. 旧版附件表升级 SQL

如果你已经按上一个版本创建过 `attachments` 表，需要执行下面这组增量 SQL，把表结构升级到“先上传附件、后绑定消息”的新方案。

```sql
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
```

这次数据库层的核心变更只有 `attachments` 表：

- `messages` 表里的 `extra_metadata` 已经存在于当前建表 SQL 中，不需要额外升级。
- `attachment_ids` 是消息请求参数，不是数据库字段，因此不需要新增列。

## 7. 后续建议

这份 SQL 已经足够支撑当前需求文档里的 MVP。

如果你下一步继续推进，最适合继续补的是：

1. Alembic 迁移脚本版本
2. SQLAlchemy ORM 模型代码
3. 基于这些表的 Repository 层代码
