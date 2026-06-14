# 采购对账申诉与回滚 CLI

一个多命令行工具，用于处理供应商账单与内部收货清单的对账、差异识别、申诉审批和回滚操作。

## 功能特性

- **数据导入**: 支持导入供应商账单和内部收货清单
- **差异检查**: 支持 dry-run 模式进行差异分析
- **批次管理**: 创建、锁定、解锁批次
- **申诉流程**: 发起申诉、审批通过/拒绝
- **回滚操作**: 支持单条或批量回滚已审批项
- **审计日志**: 完整的操作记录追踪
- **数据导出**: 导出结果、汇总和审计日志

## 安装

```bash
cd purchase-reconciliation
pip install -e .
```

## 命令结构

```
purchase-recon
├── import      # 数据导入
│   ├── bill        # 导入供应商账单
│   └── receiving   # 导入收货清单
├── diff        # 差异检查
│   └── check       # 执行差异检查（dry-run）
├── batch       # 批次管理
│   ├── create      # 创建批次
│   ├── list        # 列出批次
│   ├── show        # 显示批次详情
│   ├── lock        # 锁定批次
│   └── unlock      # 解锁批次
├── appeal      # 申诉管理
│   ├── initiate    # 发起申诉
│   ├── approve     # 审批通过
│   ├── reject      # 拒绝申诉
│   └── list        # 列出申诉
├── rollback    # 回滚操作
│   ├── item        # 回滚单条记录
│   ├── batch       # 回滚批次
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

### 1. 导入数据

```bash
# 导入供应商账单
purchase-recon import bill -f samples/supplier_bill.csv

# 导入收货清单
purchase-recon import receiving -f samples/receiving_list.csv
```

### 2. 差异检查（Dry-run）

```bash
# 仅检查不入库
purchase-recon diff check --dry-run

# 检查指定文件
purchase-recon diff check -b samples/supplier_bill.csv -r samples/receiving_list.csv
```

### 3. 创建批次

```bash
# 创建批次（自动使用上次导入的文件）
purchase-recon batch create -o 张三

# 使用指定文件创建批次
purchase-recon batch create -b samples/supplier_bill.csv -r samples/receiving_list.csv -o 张三

# Dry-run 模式创建批次（仅检查不入库）
purchase-recon batch create -o 张三 --dry-run
```

### 4. 查看批次

```bash
# 列出所有批次
purchase-recon batch list

# 查看批次详情
purchase-recon batch show -b BATCH_20240115_103000
```

### 5. 申诉流程

```bash
# 发起申诉（全部pending项）
purchase-recon appeal initiate -b BATCH_20240115_103000 -o 张三 -n "核对差异"

# 发起单条申诉
purchase-recon appeal initiate -b BATCH_20240115_103000 -o 张三 -i 1

# 审批通过（全部pending项）
purchase-recon appeal approve -b BATCH_20240115_103000 -o 李四 -n "同意申诉"

# 审批通过单条
purchase-recon appeal approve -b BATCH_20240115_103000 -o 李四 -i 1

# 拒绝申诉
purchase-recon appeal reject -b BATCH_20240115_103000 -o 李四 -n "证据不足"

# 查看申诉列表
purchase-recon appeal list -b BATCH_20240115_103000
```

### 6. 回滚操作

```bash
# 回滚单条记录
purchase-recon rollback item -b BATCH_20240115_103000 -i 1 -o 王五 -n "发现错误"

# 回滚批次（所有已审批项）
purchase-recon rollback batch -b BATCH_20240115_103000 -o 王五

# 检查回滚状态
purchase-recon rollback check -b BATCH_20240115_103000
```

### 7. 锁定/解锁批次

```bash
# 锁定批次
purchase-recon batch lock -b BATCH_20240115_103000 -o 张三

# 解锁批次
purchase-recon batch unlock -b BATCH_20240115_103000 -o 张三
```

### 8. 数据导出

```bash
# 导出批次结果
purchase-recon export result -b BATCH_20240115_103000 -o output/result.csv

# 导出汇总
purchase-recon export summary -o output/summary.csv

# 导出审计日志
purchase-recon export audit -o output/audit.csv

# 导出指定批次审计日志
purchase-recon export audit -b BATCH_20240115_103000 -o output/audit_batch.csv
```

### 9. 状态查询

```bash
# 查看所有批次状态
purchase-recon status batch

# 查看批次差异项状态
purchase-recon status item -b BATCH_20240115_103000
```

### 10. 审计日志

```bash
# 查看所有审计日志
purchase-recon audit list

# 查看指定批次审计日志
purchase-recon audit list -b BATCH_20240115_103000

# 审计汇总
purchase-recon audit summary
```

## 失败路径测试

### 1. Malformed 输入（dry-run 模式）

```bash
# 使用格式错误的文件进行 dry-run 检查
purchase-recon diff check -b samples/malformed_bill.csv --dry-run
# 预期：报错但不影响数据库
```

### 2. 已回滚项再次审批

```bash
# 先回滚一项
purchase-recon rollback item -b BATCH_xxx -i 1 -o 王五

# 尝试再次审批已回滚项
purchase-recon appeal approve -b BATCH_xxx -i 1 -o 李四
# 预期：拒绝操作，提示已回滚
```

### 3. 导出目标路径被占用

```bash
# 创建一个临时文件占用目标路径
echo "test" > output/result.csv

# 尝试导出到已存在的文件
purchase-recon export result -b BATCH_xxx -o output/result.csv
# 预期：报错，文件已存在
```

## 样例数据

样例数据位于 `samples/` 目录：
- `supplier_bill.csv`: 供应商账单样例
- `receiving_list.csv`: 收货清单样例

## 数据持久化

所有数据存储在 `~/.purchase_recon.db` SQLite 数据库中，重启 CLI 后数据仍然可用。

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