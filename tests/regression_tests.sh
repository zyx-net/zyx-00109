#!/bin/bash
# 采购对账 CLI 回归测试脚本

set -e

echo "============================================"
echo "采购对账 CLI 回归测试"
echo "============================================"
echo ""

# 清理旧的测试数据
rm -f d:/workSpace/AI__SPACE/zyx-00109/purchase_recon.db
rm -f d:/workSpace/AI__SPACE/zyx-00109/output/*.csv

echo "=== 1. 测试配置管理 ==="
echo ""
purchase-recon config rule --list
purchase-recon config rule --set --key quantity_tolerance --value 0.5
purchase-recon config rule --list
echo ""

echo "=== 2. 测试导入（含验证） ==="
echo ""
echo "--- 2.1 正常导入 ---"
purchase-recon import bill -f samples/supplier_bill.csv
purchase-recon import receiving -f samples/receiving_list.csv
echo ""

echo "--- 2.2 Malformed 文件导入验证 ---"
purchase-recon import bill -f samples/malformed_bill.csv || true
echo ""

echo "=== 3. 测试差异检查 Dry-run ==="
echo ""
purchase-recon diff check --dry-run
echo ""

echo "=== 4. 测试创建批次 ==="
echo ""
purchase-recon batch create -o 张三 -R reviewer
BATCH_NO=$(purchase-recon batch list | grep "BATCH" | head -1 | awk '{print $1}')
echo "创建的批次: $BATCH_NO"
echo ""

echo "=== 5. 测试申诉流程（角色验证） ==="
echo ""
echo "--- 5.1 发起申诉 ---"
purchase-recon appeal initiate -b "$BATCH_NO" -o 张三 -R reviewer -n "核对差异"
echo ""

echo "--- 5.2 审批通过 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R approver -n "同意申诉"
echo ""

echo "--- 5.3 查看申诉列表（含角色） ---"
purchase-recon appeal list -b "$BATCH_NO"
echo ""

echo "=== 6. 测试角色权限校验 ==="
echo ""
echo "--- 6.1 缺少角色参数 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 || echo "预期失败: 缺少角色参数"
echo ""

echo "--- 6.2 无效角色 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R invalid_role || echo "预期失败: 无效角色"
echo ""

echo "--- 6.3 权限不足 ---"
purchase-recon appeal approve -b "$BATCH_NO" -o 李四 -R reviewer || echo "预期失败: reviewer无审批权限"
echo ""

echo "=== 7. 测试回滚操作 ==="
echo ""
echo "--- 7.1 检查回滚状态 ---"
purchase-recon rollback check -b "$BATCH_NO"
echo ""

echo "--- 7.2 回滚一条记录 ---"
purchase-recon rollback item -b "$BATCH_NO" -i 1 -o 王五 -R admin -n "发现错误"
echo ""

echo "--- 7.3 权限不足的回滚 ---"
purchase-recon rollback item -b "$BATCH_NO" -i 2 -o 王五 -R approver || echo "预期失败: 仅admin可回滚"
echo ""

echo "=== 8. 测试已回滚项再次审批 ==="
echo ""
purchase-recon appeal approve -b "$BATCH_NO" -i 1 -o 李四 -R approver || echo "预期失败: 已回滚项无法审批"
echo ""

echo "=== 9. 测试导出功能 ==="
echo ""
echo "--- 9.1 导出结果 ---"
purchase-recon export result -b "$BATCH_NO" -o output/result_new.csv
echo ""

echo "--- 9.2 路径冲突检测 ---"
echo "test" > output/result_new.csv
purchase-recon export result -b "$BATCH_NO" -o output/result_new.csv || echo "预期失败: 文件已存在"
rm -f output/result_new.csv
echo ""

echo "=== 10. 测试审计日志 ==="
echo ""
purchase-recon audit list
echo ""

echo "=== 11. 跨进程查询测试 ==="
echo ""
echo "--- 11.1 重启后查询批次 ---"
purchase-recon batch list
echo ""

echo "--- 11.2 查询申诉状态 ---"
purchase-recon appeal list -b "$BATCH_NO"
echo ""

echo "============================================"
echo "回归测试完成！"
echo "============================================"