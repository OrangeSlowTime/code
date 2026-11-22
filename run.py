"""系统启动入口。

用法：
    python run.py
"""
import config
from web_app import create_app

app = create_app()

if __name__ == "__main__":
    print("=" * 64)
    print("  天猫电商大数据商业分析与智能助手平台")
    print("  访问地址: http://127.0.0.1:5000")
    print("  管理员账号: admin（密码以数据库 sys_users 为准）")
    print("=" * 64)
    app.run(host=config.HOST, port=config.PORT, debug=False)
