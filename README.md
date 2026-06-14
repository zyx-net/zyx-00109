# 采购对账申诉与回滚 CLI

一个多命令行工具，用于处理供应商账单与内部收货清单的对账、差异识别、申诉审批和回滚操作。

## 功能特性

- **数据导入**: 支持导入供应商账单和内部收货清单（含完整验证）
- **差异检查**: 支持 dry-run 模式进行差异分析
- **规则方案**: 支持创建多套对账规则方案，配置金额容差、日期偏移、必填/忽略字段
- **方案管理**: 创建、查看、切换、删除方案，跨重启持久化
- **方案应用**: 实际对账时按指定方案生效，不只是展示配置
- **方案导出/导入**: 支持方案的导入导出，含冲突处理（覆盖/跳过/改名）
- **规则快照**: 创建批次时自动保存规则快照，跨重启可追溯
- **批次管理**: 创建、锁定、解锁批次（含操作者角色）
- **申诉流程**: 发起申诉、审批通过/拒绝（需指定角色）
- **回滚操作**: 支持单条或批量回滚已审批项（仅admin角色）
- **审计日志**: 完整的操作记录追踪（含角色信息和规则快照）
- **数据导出**: 导出结果、汇总和审计日志

## 安装

```bash
cd d:/workSpace/AI__SPACE/zyx-00109
pip install -e .
```

## 角色说明

| 角色 | 权限说明 |
|------|---------|
| reviewer | 可发起申诉 |
| approver | 可发起申诉、审批通过/拒绝 |
| admin | 拥有所有权限，包括回滚 |

## 命令结构

```
purchase-recon
├── import      # 数据导入
│   ├── bill        # 导入供应商账单（含验证）
│   └── receiving   # 导入收货清单（含验证）
├── diff        # 差异检查
│   └── check       # 执行差异检查（支持方案）
├── scheme      # 方案管理
│   ├── create      # 创建方案
│   ├── list        # 列出方案
│   ├── show        # 显示方案详情
│   ├── switch      # 切换激活方案
│   ├── update      # 更新方案
│   ├── delete      # 删除方案
│   ├── export      # 导出方案
│   ├── import      # 导入方案
│   └── active      # 显示当前激活方案
├── config      # 配置管理
│   ├── set         # 设置配置
│   ├── get         # 获取配置
│   ├── list        # 列出所有配置
│   └── rule        # 对账规则管理
├── batch       # 批次管理
│   ├── create      # 创建批次（支持方案）
│   ├── list        # 列出批次
│   ├── show        # 显示批次详情
│   ├── lock        # 锁定批次
│   └── unlock      # 解锁批次
├── appeal      # 申诉管理
│   ├── initiate    # 发起申诉（需指定角色）
│   ├── approve     # 审批通过（需approver/admin角色）
│   ├── reject      # 拒绝申诉（需approver/admin角色）
│   └── list        # 列出申诉
├── rollback    # 回滚操作
│   ├── item        # 回滚单条记录（仅admin角色）
│   ├── batch       # 回滚批次（仅admin角色）
│   └── check       # 检查回滚状态
├── export      # 数据导出
│   ├── result      # 导出结果
│   ├── summary     # 导出汇总
│   └── audit       # 导出审计日志
├── status      # 状态查询
│   ├── batch       # 批次状态
│   └── item        # 差异项状态
└── audit       # 审计日志
    ├── list        # 列出审计日志
    └── summary     # 审计汇总
```

## 使用示例

### 1. 方案管理

```bash
# 创建方案（严格模式）
purchase-recon scheme create -n strict --description "严格模式" -q 0 -a 0

# 创建方案（宽松模式，含容差）
purchase-recon scheme create -n loose --description "宽松模式" -q 1.0 -a 50.0 --set-active

# 创建方案（灵活模式，含必填/忽略字段）
purchase-recon scheme create -n flexible -b "华东区" --description "灵活模式" -q 2.5 -a 100.0 -r bill_no -r item_code -i unit_price

# 列出所有方案
purchase-recon scheme list

# 查看方案详情
purchase-recon scheme show -n loose

# 切换激活方案
purchase-recon scheme switch -n strict

# 显示当前激活方案
purchase-recon scheme active

# 更新方案
purchase-recon scheme update -n strict -q 0.5 -a 25.0

# 删除方案
purchase-recon scheme delete -n to_delete -f

# 导出方案到文件
purchase-recon scheme export -o output/schemes.json

# 导入方案（同名冲突处理选项: skip/overwrite/rename）
purchase-recon scheme import -f output/schemes.json -c skip
purchase-recon scheme import -f output/schemes.json -c overwrite
purchase-recon scheme import -f output/schemes.json -c rename
```

### 2. 差异检查（使用方案）

```bash
# 使用激活方案进行差异检查
purchase-recon diff check

# 指定方案进行检查
purchase-recon diff check -s loose

# 不使用任何方案（严格匹配）
purchase-recon diff check --no-scheme
```

### 3. 导入数据

```bash
# 导入供应商账单
purchase-recon import bill -f samples/supplier_bill.csv

# 导入收货清单
purchase-recon import receiving -f samples/receiving_list.csv
```

### 4. 创建批次（使用方案）

```bash
# 使用激活方案创建批次
purchase-recon batch create -o 张三 -R reviewer

# 指定方案创建批次
purchase-recon batch create -o 张三 -R reviewer -s strict

# 不使用方案创建批次
purchase-recon batch create -o 张三 -R reviewer --no-scheme

# Dry-run 模式
purchase-recon batch create -o 张三 -R reviewer --dry-run
```

### 5. 申诉流程

```bash
# 发起申诉（需要指定角色）
purchase-recon appeal initiate -b BATCH_20260615_002450 -o 张三 -R reviewer -n "核对差异"

# 审批通过（需要approver或admin角色）
purchase-recon appeal approve -b BATCH_20260615_002450 -o 李四 -R approver -n "同意申诉"

# 拒绝申诉
purchase-recon appeal reject -b BATCH_20260615_002450 -o 李四 -R approver -n "证据不足"

# 查看申诉列表
purchase-recon appeal list -b BATCH_20260615_002450
```

### 6. 回滚操作（仅admin角色）

```bash
# 回滚单条记录
purchase-recon rollback item -b BATCH_20260615_002450 -i 1 -o 王五 -R admin -n "发现错误"

# 回滚批次
purchase-recon rollback batch -b BATCH_20260615_002450 -o 王五 -R admin

# 检查回滚状态
purchase-recon rollback check -b BATCH_20260615_002450
```

### 7. 锁定/解锁批次

```bash
# 锁定批次
purchase-recon batch lock -b BATCH_20260615_002450 -o 张三

# 解锁批次
purchase-recon batch unlock -b BATCH_20260615_002450 -o 张三
```

### 8. 数据导出

```bash
# 导出批次结果
purchase-recon export result -b BATCH_20260615_002450 -o output/result.csv

# 导出汇总
purchase-recon export summary -o output/summary.csv

# 导出审计日志
purchase-recon export audit -o output/audit.csv

# 导出指定批次审计日志
purchase-recon export audit -b BATCH_20260615_002450 -o output/audit_batch.csv
```

### 9. 状态查询

```bash
# 查看所有批次状态
purchase-recon status batch

# 查看批次差异项状态
purchase-recon status item -b BATCH_20260615_002450
```

### 10. 审计日志

```bash
# 查看所有审计日志
purchase-recon audit list

# 查看指定批次审计日志
purchase-recon audit list -b BATCH_20260615_002450

# 审计汇总
purchase-recon audit summary
```

## 方案参数说明

创建方案时可配置以下参数：

| 参数 | 短选项 | 说明 |
|------|--------|------|
| --name | -n | 方案名称（唯一标识） |
| --business-line | -b | 业务线名称 |
| --description | -d | 方案描述 |
| --quantity-tolerance | -q | 数量容差（允许的数量差异） |
| --amount-tolerance | -a | 金额容差（允许的金额差异） |
| --date-offset | - | 日期偏移天数（正数延后，负数提前） |
| --required-fields | -r | 必填字段（可多次指定） |
| --ignored-fields | -i | 忽略字段（可多次指定） |
| --set-active | - | 创建后设为激活方案 |

## 规则快照功能

创建批次时，系统会自动保存当前生效方案的规则快照到批次记录中。这意味着：

1. **跨重启可追溯**: 即使方案被修改或删除，历史批次仍然保留创建时的规则快照
2. **复查无忧**: 查看批次时可以看到创建时使用的具体规则参数
3. **日志完整**: 申诉列表、审计日志等都会显示对应的规则快照

### 规则快照包含的信息

- 方案名称
- 业务线和描述
- 数量容差和金额容差
- 日期偏移天数
- 必填字段列表
- 忽略字段列表

### 示例输出

```
批次信息:
  批次编号: BATCH_20260615_002450
  状态: open
  方案: strict
  规则快照: 方案:strict; 数量容差±0; 金额容差±0; 日期偏移0天
  创建时间: 2026-06-15 00:24:50
  锁定人: 无
  锁定时间: 无
```

## 差异检查输出说明

使用方案进行差异检查时，输出会显示：

1. **使用方案信息**: 显示当前使用的方案名称和参数
2. **容差放过的差异**: 数量和金额差异在容差范围内的记录
3. **仍然失败的差异**: 超出容差范围的记录

```
检查完成:
  实际差异: 5 条
  容差放过: 3 条
------------------------------------------------------------

【容差放过的差异】(3 条):
... 表格显示容差放过的记录及原因 ...

【仍然失败的差异】(5 条):
... 表格显示仍然需要处理的记录 ...
```

## 失败路径测试

### 1. Malformed 输入（dry-run 模式）

```bash
# 使用格式错误的文件进行 dry-run 检查
purchase-recon diff check -b samples/malformed_bill.csv -r samples/receiving_list.csv --dry-run
# 预期：列出所有错误行，不落库
```

### 2. 角色校验失败

```bash
# 缺少角色参数
purchase-recon appeal approve -b BATCH_xxx -o 李四
# 预期：报错，缺少必要参数 --role/-R

# 无效角色
purchase-recon appeal approve -b BATCH_xxx -o 李四 -R invalid_role
# 预期：报错，无效的角色

# 权限不足
purchase-recon appeal approve -b BATCH_xxx -o 李四 -R reviewer
# 预期：报错，reviewer角色没有审批权限

# 回滚权限不足
purchase-recon rollback item -b BATCH_xxx -i 1 -o 王五 -R approver
# 预期：报错，仅admin角色可执行回滚
```

### 3. 方案相关测试

```bash
# 创建同名方案
purchase-recon scheme create -n my_scheme
purchase-recon scheme create -n my_scheme
# 预期：报错，方案已存在

# 切换不存在的方案
purchase-recon scheme switch -n non_existent
# 预期：报错，方案不存在

# 删除激活方案
purchase-recon scheme delete -n active_scheme
# 预期：可以删除，不会影响其他方案

# 导入同名方案（skip）
purchase-recon scheme import -f schemes.json -c skip
# 预期：跳过已存在的方案

# 导入同名方案（overwrite）
purchase-recon scheme import -f schemes.json -c overwrite
# 预期：覆盖已存在的方案

# 导入同名方案（rename）
purchase-recon scheme import -f schemes.json -c rename
# 预期：创建带编号的新方案名
```

### 4. 导出目标路径被占用

```bash
# 创建一个临时文件占用目标路径
echo "test" > output/result.csv

# 尝试导出到已存在的文件
purchase-recon export result -b BATCH_xxx -o output/result.csv
# 预期：报错，目标文件已存在
```

### 5. 回滚冲突检测

```bash
# 检查批次是否有回滚冲突
purchase-recon rollback check -b BATCH_xxx
# 预期：显示回滚状态和冲突信息
```

## 样例数据

样例数据位于 `samples/` 目录：
- `supplier_bill.csv`: 供应商账单样例
- `receiving_list.csv`: 收货清单样例
- `malformed_bill.csv`: 格式错误样例（用于测试验证）

## 数据持久化

所有数据存储在 SQLite 数据库中，重启 CLI 后数据仍然可用：
- 方案数据
- 批次数据
- 差异项数据
- 审计日志

## 申诉状态说明

| 状态 | 说明 |
|------|------|
| pending | 待申诉/待审批 |
| approved | 已审批通过 |
| rejected | 已拒绝 |
| rolled_back | 已回滚 |

## 批次状态说明

| 状态 | 说明 |
|------|------|
| open | 开放状态，可进行申诉操作 |
| locked | 已锁定，禁止申诉操作 |
| completed | 已完成 |

## 运行测试

### 单元测试

```bash
cd d:/workSpace/AI__SPACE/zyx-00109
pip install pytest
pytest tests/test_scheme.py -v
```

### 回归测试

```bash
cd d:/workSpace/AI__SPACE/zyx-00109
bash tests/regression_tests.sh
```
