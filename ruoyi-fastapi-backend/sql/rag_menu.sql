-- RAG模块菜单配置SQL
-- 执行此脚本添加RAG模块菜单

-- 一级菜单：RAG知识库
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2000, 'RAG知识库', 0, 10, 'rag', NULL, NULL, '', 1, 0, 'M', '0', '0', '', 'documentation', 'admin', CURRENT_TIMESTAMP, 'RAG知识库管理');

-- 二级菜单：知识库管理
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2001, '知识库管理', 2000, 1, 'knowledge-base', 'rag/knowledge-base/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:kb:list', 'tree', 'admin', CURRENT_TIMESTAMP, '知识库管理菜单');

-- 知识库管理按钮权限
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2002, '知识库查询', 2001, 1, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:query', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2003, '知识库新增', 2001, 2, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:add', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2004, '知识库修改', 2001, 3, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:edit', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2005, '知识库删除', 2001, 4, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:kb:remove', '#', 'admin', CURRENT_TIMESTAMP, '');

-- 二级菜单：文档管理
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2010, '文档管理', 2000, 2, 'document', 'rag/document/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:doc:list', 'documentation', 'admin', CURRENT_TIMESTAMP, '文档管理菜单');

-- 文档管理按钮权限
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2011, '文档查询', 2010, 1, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:query', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2012, '文档上传', 2010, 2, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:add', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2013, '文档修改', 2010, 3, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:edit', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2014, '文档删除', 2010, 4, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:doc:remove', '#', 'admin', CURRENT_TIMESTAMP, '');

-- 二级菜单：知识查询
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2020, '知识查询', 2000, 3, 'query', 'rag/query/index', NULL, '', 1, 0, 'C', '0', '0', 'rag:query:execute', 'search', 'admin', CURRENT_TIMESTAMP, '知识查询菜单');

-- 知识查询按钮权限
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2021, '执行查询', 2020, 1, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:query:execute', '#', 'admin', CURRENT_TIMESTAMP, '');
INSERT INTO sys_menu (menu_id, menu_name, parent_id, order_num, path, component, query, route_name, is_frame, is_cache, menu_type, visible, status, perms, icon, create_by, create_time, remark)
VALUES (2022, '查询记录', 2020, 2, '', NULL, NULL, '', 1, 0, 'F', '0', '0', 'rag:query:logs', '#', 'admin', CURRENT_TIMESTAMP, '');
