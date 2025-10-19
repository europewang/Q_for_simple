"""
数据管理器 - 负责K线数据的缓存和获取
"""
import os
import pickle
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from binance.client import Client
from dotenv import load_dotenv


class DataManager:
    """数据管理器类，负责K线数据的缓存和获取"""
    
    def __init__(self):
        """初始化数据管理器"""
        self.cache_dir = "temp/data_cache"
        self.client = None
        
        # 确保缓存目录存在
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # 初始化Binance客户端
        self._init_binance_client()
    
    def _init_binance_client(self):
        """初始化Binance API客户端"""
        load_dotenv()
        api_key = os.getenv('API_KEY')
        api_secret = os.getenv('API_SECRET')
        
        # 代理设置
        proxies = {}
        if os.getenv('HTTP_PROXY'):
            proxies['http'] = os.getenv('HTTP_PROXY')
        if os.getenv('HTTPS_PROXY'):
            proxies['https'] = os.getenv('HTTPS_PROXY')
        
        try:
            if proxies:
                self.client = Client(api_key, api_secret, requests_params={'proxies': proxies, 'timeout': 30})
            else:
                self.client = Client(api_key, api_secret, requests_params={'timeout': 30})
            
            # 测试连接
            self.client.ping()
            print("✓ DataManager: 成功连接到Binance API")
        except Exception as e:
            print(f"✗ DataManager: 连接Binance API失败: {e}")
            raise
    
    def _generate_cache_filename(self, symbol, start_date, end_date, interval):
        """生成缓存文件名"""
        # 使用符号、日期和时间间隔生成唯一的文件名
        cache_key = f"{symbol}_{start_date}_{end_date}_{interval}"
        return f"{cache_key}.pkl"
    
    def _is_cache_valid(self, cache_file_path, max_age_hours=24):
        """检查缓存文件是否有效"""
        if not os.path.exists(cache_file_path):
            return False
        
        # 检查文件修改时间
        file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file_path))
        current_time = datetime.now()
        
        # 如果文件超过指定小时数，认为过期
        if (current_time - file_mtime).total_seconds() > max_age_hours * 3600:
            return False
        
        return True
    
    def _load_from_cache(self, cache_file_path):
        """从缓存文件加载数据"""
        try:
            with open(cache_file_path, 'rb') as f:
                data = pickle.load(f)
            print(f"✓ 从缓存加载数据: {os.path.basename(cache_file_path)}")
            return data
        except Exception as e:
            print(f"✗ 加载缓存失败: {e}")
            return None
    
    def _save_to_cache(self, data, cache_file_path):
        """保存数据到缓存文件"""
        try:
            with open(cache_file_path, 'wb') as f:
                pickle.dump(data, f)
            print(f"✓ 数据已缓存: {os.path.basename(cache_file_path)}")
        except Exception as e:
            print(f"✗ 保存缓存失败: {e}")
    
    def _fetch_from_binance(self, symbol, start_date, end_date, interval):
        """从Binance API获取数据"""
        print(f"正在从Binance获取 {symbol} {interval} 数据...")
        
        # 映射时间间隔
        interval_map = {
            '1m': Client.KLINE_INTERVAL_1MINUTE,
            '30m': Client.KLINE_INTERVAL_30MINUTE,
            '1h': Client.KLINE_INTERVAL_1HOUR,
            '4h': Client.KLINE_INTERVAL_4HOUR,
            '1d': Client.KLINE_INTERVAL_1DAY
        }
        
        if interval not in interval_map:
            raise ValueError(f"不支持的时间间隔: {interval}")
        
        try:
            klines = self.client.get_historical_klines(
                symbol, interval_map[interval], start_date, end_date
            )
            
            # 转换为DataFrame
            df = self._klines_to_dataframe(klines)
            print(f"✓ 从Binance获取到 {len(df)} 根 {interval} K线")
            return df
            
        except Exception as e:
            print(f"✗ 从Binance获取数据失败: {e}")
            raise
    
    def _klines_to_dataframe(self, klines):
        """将K线数据转换为DataFrame"""
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # 转换数据类型
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        return df
    
    def _check_local_monthly_data(self, symbol, start_date, end_date, interval):
        """
        检查本地月度数据文件是否存在
        
        Args:
            symbol: 交易对符号
            start_date: 开始日期
            end_date: 结束日期
            interval: 时间间隔
            
        Returns:
            pandas.DataFrame or None: 如果找到本地数据则返回合并后的数据，否则返回None
        """
        monthly_data_dir = "output/monthly_data"
        if not os.path.exists(monthly_data_dir):
            return None
            
        # 生成月份范围
        monthly_ranges = self._generate_monthly_ranges(start_date, end_date)
        all_data = []
        missing_months = []
        
        for month_range in monthly_ranges:
            # 构建月度文件名
            monthly_filename = f"{symbol}_{month_range['month_name']}_{interval}.pkl"
            monthly_file_path = os.path.join(monthly_data_dir, monthly_filename)
            
            if os.path.exists(monthly_file_path):
                try:
                    # 加载本地月度数据
                    monthly_data = self._load_from_cache(monthly_file_path)
                    if monthly_data is not None and not monthly_data.empty:
                        all_data.append(monthly_data)
                        print(f"✓ 使用本地数据: {monthly_filename}")
                    else:
                        missing_months.append(month_range)
                except Exception as e:
                    print(f"⚠ 加载本地数据失败 {monthly_filename}: {e}")
                    missing_months.append(month_range)
            else:
                missing_months.append(month_range)
        
        # 如果有缺失的月份，返回None让系统去联网获取
        if missing_months:
            print(f"⚠ 缺失 {len(missing_months)} 个月的本地数据，将联网获取")
            return None
            
        # 合并所有本地数据
        if all_data:
            combined_data = pd.concat(all_data, ignore_index=True)
            # 按时间排序并去重
            combined_data = combined_data.sort_values('open_time').drop_duplicates(subset=['open_time'])
            combined_data.reset_index(drop=True, inplace=True)
            
            # 根据日期范围过滤数据
            start_dt = self._parse_date_string(start_date)
            end_dt = self._parse_date_string(end_date)
            
            # 转换时间戳为datetime
            combined_data['datetime'] = pd.to_datetime(combined_data['open_time'], unit='ms')
            filtered_data = combined_data[
                (combined_data['datetime'] >= start_dt) & 
                (combined_data['datetime'] <= end_dt)
            ].drop('datetime', axis=1)
            
            print(f"✓ 成功使用本地数据，共 {len(filtered_data)} 条记录")
            return filtered_data
            
        return None

    def get_kline_data(self, symbol, start_date, end_date, interval='30m', force_refresh=False):
        """
        获取K线数据（优先从本地月度数据获取）
        
        Args:
            symbol: 交易对符号，如 'BTCUSDT'
            start_date: 开始日期，如 '2024-01-01'
            end_date: 结束日期，如 '2024-01-31'
            interval: 时间间隔，支持 '1m', '30m', '1h', '4h', '1d'
            force_refresh: 是否强制刷新缓存
        
        Returns:
            pandas.DataFrame: K线数据
        """
        # 如果不强制刷新，优先检查本地月度数据
        if not force_refresh:
            local_data = self._check_local_monthly_data(symbol, start_date, end_date, interval)
            if local_data is not None:
                return local_data
        
        # 生成缓存文件名
        cache_filename = self._generate_cache_filename(symbol, start_date, end_date, interval)
        cache_file_path = os.path.join(self.cache_dir, cache_filename)
        
        # 如果不强制刷新，再检查普通缓存
        if not force_refresh and self._is_cache_valid(cache_file_path):
            data = self._load_from_cache(cache_file_path)
            if data is not None:
                print(f"✓ 使用缓存数据: {cache_filename}")
                return data

        # 从Binance API获取数据
        print(f"📡 从Binance API获取数据...")
        data = self._fetch_from_binance(symbol, start_date, end_date, interval)
        
        # 保存到缓存
        self._save_to_cache(data, cache_file_path)
        
        return data
    
    def get_multiple_intervals(self, symbol, start_date, end_date, intervals=['30m', '1m'], force_refresh=False):
        """
        获取多个时间间隔的K线数据
        
        Args:
            symbol: 交易对符号
            start_date: 开始日期
            end_date: 结束日期
            intervals: 时间间隔列表
            force_refresh: 是否强制刷新缓存
        
        Returns:
            dict: 包含不同时间间隔数据的字典
        """
        result = {}
        for interval in intervals:
            result[interval] = self.get_kline_data(symbol, start_date, end_date, interval, force_refresh)
        return result
    
    def _parse_date_string(self, date_str):
        """解析日期字符串为datetime对象"""
        try:
            # 尝试解析 "1 Jan, 2024" 格式
            return datetime.strptime(date_str, "%d %b, %Y")
        except ValueError:
            try:
                # 尝试解析 "2024-01-01" 格式
                return datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"无法解析日期格式: {date_str}")
    
    def _generate_monthly_ranges(self, start_date, end_date):
        """生成月份范围列表"""
        start_dt = self._parse_date_string(start_date)
        end_dt = self._parse_date_string(end_date)
        
        monthly_ranges = []
        current_date = start_dt.replace(day=1)  # 从月初开始
        
        while current_date <= end_dt:
            # 计算当月的结束日期
            next_month = current_date + relativedelta(months=1)
            month_end = next_month - timedelta(days=1)
            
            # 如果月末超过了结束日期，使用结束日期
            if month_end > end_dt:
                month_end = end_dt
            
            # 如果当前月的开始日期小于实际开始日期，使用实际开始日期
            month_start = max(current_date, start_dt)
            
            monthly_ranges.append({
                'start': month_start.strftime("%d %b, %Y"),
                'end': month_end.strftime("%d %b, %Y"),
                'month_name': current_date.strftime("%Y-%m")
            })
            
            current_date = next_month
        
        return monthly_ranges
    
    def get_kline_data_monthly(self, symbol, start_date, end_date, interval='30m', 
                              force_refresh=False, save_monthly_files=True, monthly_output_dir=None):
        """
        按月份拆分获取K线数据
        
        Args:
            symbol: 交易对符号
            start_date: 开始日期
            end_date: 结束日期
            interval: 时间间隔
            force_refresh: 是否强制刷新缓存
            save_monthly_files: 是否保存月度文件
            monthly_output_dir: 月度文件输出目录
        
        Returns:
            pandas.DataFrame: 合并后的完整K线数据
        """
        print(f"开始按月份获取 {symbol} {interval} 数据...")
        
        # 生成月份范围
        monthly_ranges = self._generate_monthly_ranges(start_date, end_date)
        print(f"将分 {len(monthly_ranges)} 个月份获取数据")
        
        # 创建月度输出目录
        if save_monthly_files and monthly_output_dir:
            if not os.path.exists(monthly_output_dir):
                os.makedirs(monthly_output_dir)
        
        all_data = []
        
        for i, month_range in enumerate(monthly_ranges, 1):
            print(f"\n[{i}/{len(monthly_ranges)}] 获取 {month_range['month_name']} 数据...")
            print(f"  时间范围: {month_range['start']} 至 {month_range['end']}")
            
            try:
                # 获取当月数据
                monthly_data = self.get_kline_data(
                    symbol, month_range['start'], month_range['end'], 
                    interval, force_refresh
                )
                
                if not monthly_data.empty:
                    all_data.append(monthly_data)
                    print(f"  ✓ 获取到 {len(monthly_data)} 条数据")
                    
                    # 保存月度文件
                    if save_monthly_files and monthly_output_dir:
                        monthly_filename = f"{symbol}_{month_range['month_name']}_{interval}.pkl"
                        monthly_file_path = os.path.join(monthly_output_dir, monthly_filename)
                        self._save_to_cache(monthly_data, monthly_file_path)
                        print(f"  ✓ 月度数据已保存: {monthly_filename}")
                else:
                    print(f"  ⚠ 该月份没有数据")
                    
            except Exception as e:
                print(f"  ✗ 获取 {month_range['month_name']} 数据失败: {e}")
                continue
        
        # 合并所有月份的数据
        if all_data:
            combined_data = pd.concat(all_data, ignore_index=True)
            # 按时间排序并去重
            combined_data = combined_data.sort_values('open_time').drop_duplicates(subset=['open_time'])
            combined_data.reset_index(drop=True, inplace=True)
            
            print(f"\n✓ 所有月份数据合并完成，共 {len(combined_data)} 条数据")
            return combined_data
        else:
            print("\n✗ 没有获取到任何数据")
            return pd.DataFrame()
    
    def clear_cache(self, symbol=None, older_than_days=None):
        """
        清理缓存文件
        
        Args:
            symbol: 指定清理某个交易对的缓存，None表示清理所有
            older_than_days: 清理多少天前的缓存，None表示清理所有
        """
        if not os.path.exists(self.cache_dir):
            return
        
        files_removed = 0
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.pkl'):
                continue
            
            file_path = os.path.join(self.cache_dir, filename)
            
            # 检查是否匹配指定的交易对
            if symbol and not filename.startswith(symbol):
                continue
            
            # 检查文件年龄
            if older_than_days:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (datetime.now() - file_mtime).days < older_than_days:
                    continue
            
            try:
                os.remove(file_path)
                files_removed += 1
                print(f"✓ 删除缓存文件: {filename}")
            except Exception as e:
                print(f"✗ 删除缓存文件失败 {filename}: {e}")
        
        print(f"共删除 {files_removed} 个缓存文件")
    
    def list_cache_files(self):
        """列出所有缓存文件"""
        if not os.path.exists(self.cache_dir):
            print("缓存目录不存在")
            return
        
        cache_files = []
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.pkl'):
                file_path = os.path.join(self.cache_dir, filename)
                file_size = os.path.getsize(file_path)
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                cache_files.append({
                    'filename': filename,
                    'size_kb': round(file_size / 1024, 2),
                    'modified_time': file_mtime.strftime('%Y-%m-%d %H:%M:%S')
                })
        
        if cache_files:
            print("\n缓存文件列表:")
            print("-" * 80)
            print(f"{'文件名':<40} {'大小(KB)':<10} {'修改时间':<20}")
            print("-" * 80)
            for file_info in cache_files:
                print(f"{file_info['filename']:<40} {file_info['size_kb']:<10} {file_info['modified_time']:<20}")
        else:
            print("没有找到缓存文件")


# 创建全局数据管理器实例
data_manager = DataManager()