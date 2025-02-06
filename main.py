import tkinter as tk
from ttkbootstrap import Style, Progressbar, Treeview
import dns.resolver
import threading
import time
import os
from concurrent.futures import ThreadPoolExecutor


class DNSTester:
    def __init__(self):
        self.window = tk.Tk()
        self.style = Style(theme='flatly')
        self.results = []
        self.servers = []
        self.completed_tests = 0  # 用于跟踪已完成的测试数量
        self.test_domain = tk.StringVar()  # 用于存储用户输入的域名

        # 设置窗口标题
        self.window.title("DNS 服务器测试工具")  # 添加窗口标题

        # GUI组件初始化
        self.create_widgets()
        self.load_dns_list()
        self.show_initial_table()  # 显示初始表格

        # 配置颜色标签
        self.configure_tags()

    def create_widgets(self):
        # 输入框和标签
        input_frame = tk.Frame(self.window)
        input_frame.pack(pady=10, padx=10, anchor='w')  # 使用 anchor='w' 靠左对齐

        input_label = tk.Label(input_frame, text="请输入待测网址：")
        input_label.pack(side='left')

        self.domain_entry = tk.Entry(input_frame, textvariable=self.test_domain, width=40)
        self.domain_entry.pack(side='left', padx=10)
        self.test_domain.set("example.com")  # 设置默认值

        # 表格容器
        self.treeview_frame = tk.Frame(self.window)  # 容器用于放置表格和滚动条
        self.treeview_frame.pack(pady=10, fill='both', expand=True)

        # 垂直滚动条
        self.scrollbar = tk.Scrollbar(self.treeview_frame, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")

        # 表格
        self.treeview = Treeview(
            self.treeview_frame,
            columns=('server', 'latency'),
            show='headings',
            style='Treeview',
            height=15,
            yscrollcommand=self.scrollbar.set
        )
        self.treeview.pack(side="left", fill="both", expand=True)

        # 配置滚动条
        self.scrollbar.config(command=self.treeview.yview)

        # 设置表头
        self.treeview.heading('server', text='DNS 服务器')
        self.treeview.heading('latency', text='响应时间 (ms)')
        self.treeview.column('latency', anchor='e')

        # 测试按钮
        self.test_btn = tk.Button(
            self.window,
            text="开始测试",
            command=self.start_test_thread,
            width=20
        )
        self.test_btn.pack(pady=10)

        # 进度条和进度标签的容器
        self.progress_container = tk.Frame(self.window)
        self.progress_container.pack(side="bottom", fill="x", pady=10)

        # 进度条
        self.progress = Progressbar(self.progress_container, length=300)
        self.progress.pack(side="left", padx=10)

        # 进度显示标签
        self.progress_label = tk.Label(self.progress_container, text="进度: 0%")
        self.progress_label.pack(side="left")

    def load_dns_list(self):
        """从 dns_servers.txt 加载 DNS 服务器列表，忽略以 # 开头的注释行"""
        if not os.path.exists('dns_servers.txt'):
            print("未找到 dns_servers.txt 文件")
            return

        with open('dns_servers.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.servers.append(line)

        print(f"加载了 {len(self.servers)} 个 DNS 服务器")

    def show_initial_table(self):
        """在表格中显示所有 DNS 服务器，初始状态显示为 '未测试'"""
        for server in self.servers:
            self.treeview.insert('', 'end', values=(server, "未测试"))

    def test_dns(self, server, domain):
        """测试单个 DNS 服务器的响应时间"""
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server]
        start = time.time()
        try:
            resolver.resolve(domain, 'A', lifetime=3)
            return server, time.time() - start  # 返回服务器地址和响应时间
        except:
            return server, float('inf')  # 返回服务器地址和超时标记

    def configure_tags(self):
        """配置颜色标签"""
        self.treeview.tag_configure('green', foreground='#008000')  # 绿色
        self.treeview.tag_configure('yellow', foreground='#FFD700')  # 金黄色
        self.treeview.tag_configure('orange', foreground='#FFA500')  # 橙色
        self.treeview.tag_configure('red', foreground='#FF0000')  # 红色

    def update_table(self, server, latency):
        """更新表格中的单个条目"""
        for item in self.treeview.get_children():
            values = self.treeview.item(item, 'values')
            if values[0] == server:
                if latency == float('inf'):
                    self.treeview.set(item, 'latency', "超时")
                    self.treeview.item(item, tags=('red',))  # 添加标签
                else:
                    self.treeview.set(item, 'latency', f"{latency * 1000:.2f} ms")
                    if latency * 1000 < 50:
                        self.treeview.item(item, tags=('green',))
                    elif latency * 1000 < 200:
                        self.treeview.item(item, tags=('yellow',))
                    elif latency * 1000 < 500:
                        self.treeview.item(item, tags=('orange',))
                    else:
                        self.treeview.item(item, tags=('red',))
                break
        self.window.update_idletasks()  # 强制刷新界面

    def start_test_thread(self):
        """启动测试线程，并禁用输入框和按钮"""
        self.domain = self.test_domain.get()  # 保存用户输入的域名
        self.domain_entry.config(state='disabled')  # 禁用输入框
        self.test_btn.config(state='disabled')  # 禁用按钮
        threading.Thread(target=self.run_tests).start()

    def run_tests(self):
        """运行 DNS 服务器测试"""
        total_servers = len(self.servers)
        self.completed_tests = 0  # 重置已完成的测试数量
        self.results = []  # 清空结果列表
        domain = self.domain  # 使用保存的域名

        # 使用线程池并发测试
        with ThreadPoolExecutor(max_workers=10) as executor:
            for server in self.servers:
                future = executor.submit(self.test_dns, server, domain)
                future.add_done_callback(lambda f: self.process_result(f, total_servers))

        # 等待所有线程完成
        while len(self.results) < total_servers:
            time.sleep(0.1)

        self.results.sort(key=lambda x: x[1])  # 按响应时间排序
        self.show_sorted_results()

        # 测试完成后重新启用输入框和按钮
        self.domain_entry.config(state='normal')
        self.test_btn.config(state='normal')

    def process_result(self, future, total_servers):
        """处理线程池返回的结果"""
        server, latency = future.result()  # 从结果中解包服务器地址和响应时间
        self.results.append((server, latency))
        self.completed_tests += 1  # 更新已完成的测试数量
        self.update_progress(self.completed_tests, total_servers)  # 更新进度条和标签
        self.update_table(server, latency)  # 更新表格

    def update_progress(self, current, total):
        """更新进度条和进度显示标签"""
        progress_value = int((current / total) * 100)
        self.progress['value'] = progress_value
        self.progress_label.config(text=f"进度: {current}/{total} ({progress_value}%)")
        self.window.update_idletasks()

    def show_sorted_results(self):
        """清空表格并重新插入排序后的结果"""
        # 清空表格
        for row in self.treeview.get_children():
            self.treeview.delete(row)

        # 插入排序后的结果，并设置颜色标签
        for server, latency in self.results:
            if latency == float('inf'):
                latency_str = "超时"
                tags = ('red',)
            else:
                latency_str = f"{latency * 1000:.2f} ms"
                if latency * 1000 < 50:
                    tags = ('green',)
                elif latency * 1000 < 200:
                    tags = ('yellow',)
                elif latency * 1000 < 500:
                    tags = ('orange',)
                else:
                    tags = ('red',)
            self.treeview.insert('', 'end', values=(server, latency_str), tags=tags)


if __name__ == '__main__':
    app = DNSTester()
    app.window.mainloop()