import json
import keyboard
import os
import random
import re
import requests
import sys
import threading
import time
import UnityPy
import zipfile
from Crypto.Cipher import AES
from enum import Enum
from io import BytesIO
from pathlib import Path
from tqdm import tqdm

def printc(*string: str, color: list[int] or list[list[int]] = list(), sep: str = ' ', start: str = '', end: str = '\n', show_time: bool = True, log = print) -> None:
    log(start + ('\033[1;30m[{}]\033[0m '.format(time.strftime('%H:%M:%S')) if show_time else '') +
        sep.join('\033[{}m{}\033[0m'.format(
        ';'.join(str(c) for c in (color if len(color) == 0 else (color[i] if isinstance(color[0], list) else color))),
        string[i]) for i in range(len(string))), end=end)

back = lambda n = 1, log = print: log('\r\033[{}A'.format(n), end='\r')
next = lambda n = 1, log = print: log(n * '\n', end='')
clear = lambda log = print: log('\r\033[K', end='\r')
save = lambda log = print: log('\r\033[s', end='')
recover = lambda log = print: log('\r\033[u', end='')

def scale(n, size: int or float = 1024, digit: int = 2, unit: list[str] = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']):
    count = 0
    l = len(unit)
    def _scale(n, s) -> float:
        nonlocal count
        if n > s and count < l:
            count += 1
            return _scale(n / s, s)
        else:
            return n
    return '{{:.{}f}}{{}}'.format(digit).format(_scale(n, size), unit[count])


class ArkAssets:

    CHAT_MASK = 'UITpAi82pHAWwnzqHRMCwPonJLIB3WCl'
    
    class Servers(Enum):
        OFFICAL = 0
        BILIBILI = 1
    
    @staticmethod
    def text_asset_decrypt(stream) -> bytes:
        aes_key = ArkAssets.CHAT_MASK[:16].encode()
        aes_iv  = bytearray(16)
        data = stream[128:]
        buf  = data[:16]
        mask = ArkAssets.CHAT_MASK[16:].encode()
        for i in range(len(buf)):
            aes_iv[i] = buf[i] ^ mask[i]
        aes_obj = AES.new(aes_key, AES.MODE_CBC, aes_iv)
        decrypt_buf = aes_obj.decrypt(data[16:])
        unpad = lambda s: s[0:(len(s) - s[-1])]
        return unpad(decrypt_buf)

    @staticmethod
    def get_version(server: Servers = Servers.OFFICAL) -> tuple[str, str]:
        js = requests.get('https://ak-conf.hypergryph.com/config/prod/{}/Android/version'.format(
            'official' if server == ArkAssets.Servers.OFFICAL else 'b')).json()
        return js['resVersion'], js['clientVersion']

    def __init__(self, server: Servers = Servers.OFFICAL) -> None:
        self.server = server
        self.asset_version, self.client_Version = ArkAssets.get_version(self.server)
        printc('游戏版本: {} 素材版本: {}'.format(self.client_Version, self.asset_version), color=[1, 32])
        self.hot_update_list, self.total_size, self.ab_size = self.get_hot_update_list()
        printc('总资源大小: {} 解压后大小: {}'.format(scale(self.total_size), scale(self.ab_size)), color=[1, 32])

    def get_hot_update_list(self) -> tuple[dict, int, int]:
        js = requests.get('https://ak.hycdn.cn/assetbundle/{}/Android/assets/{}/hot_update_list.json'.format(
            'official' if self.server == ArkAssets.Servers.OFFICAL else 'bilibili',
            self.asset_version)).json()
        out = {'other': {'totalSize': 0, 'files': dict()}}
        total_size = 0
        ab_size = 0
        for item in js['packInfos']:
            k = item['name'].replace('_', '/')
            out[k] = {'totalSize': 0}
            out[k]['files'] = dict()

        def add_other(_item: dict):
            _size = _item['totalSize']
            out['other']['totalSize'] += _size
            out['other']['files'][_item['name']] = {
                'totalSize': _size,
                'abSize': _item['abSize'],
                'md5': _item['md5']
            }

        for item in js['abInfos']:
            _size = item['totalSize']
            total_size += _size
            _ab_size = item['abSize']
            ab_size += _ab_size
            if 'pid' in item:
                pid = item['pid'].replace('_', '/')
                if pid in out:
                        out[pid]['totalSize'] += _size
                        out[pid]['files'][item['name']] = {
                        'totalSize': _size,
                        'abSize': _ab_size,
                        'md5': item['md5']
                    }
                else:
                    add_other(item)
            else:
                add_other(item)
        return out, total_size, ab_size

    def download(self, savedir: str) -> None:
        options = list()
        _i = 0
        for item in self.hot_update_list:
            _size = self.hot_update_list[item]['totalSize']
            _per = _size / self.total_size
            options.append((item, '{:<35}{:<7}{}'.format('{:<15} 包大小: {}'.format(item, scale(_size)), '{:.2f}%'.format(_per * 100), int(_per * (os.get_terminal_size().columns - 46)) *'█'), [1, 34]))
            printc(options[_i][1], color=options[_i][2])
            _i += 1
        del _i
        printc('下载选项 [全部下载=A，选择下载=C，取消=Other]: ', color=[1, 36])
        inp = sys.stdin.readline().strip('\n')
        back()
        if inp == 'A' or inp == 'a':
            back()
            clear()
            printc('开始全部下载', color=[1, 36])
            self.download_fromlist([item for item in self.hot_update_list], savedir)
        elif inp == 'C' or inp == 'c':
            choosen = list()
            _pos = 0
            back()
            clear()
            printc('总数量: {} 预计大小: {} 已选择: {}'.format(sum(len(self.hot_update_list[key]['files']) for key in choosen), scale(sum(self.hot_update_list[key]['totalSize'] for key in choosen)), [key for key in choosen]), color=[1, 36])
            printc('[上下箭头=选择, 左箭头=添加, 右箭头=删除, ESC键=确认]', color=[1, 33], end=' ')
            def on_up():
                nonlocal _pos
                if _pos - 1 >= 0:
                    clear()
                    printc(options[_pos][1], color=options[_pos][2], end='\r')
                    back()
                    _pos -= 1
                    printc(options[_pos][1], color=options[_pos][2] + [100], end='\r')
            def on_down():
                nonlocal _pos
                if _pos + 1 <= len(options) - 1:
                    clear()
                    printc(options[_pos][1], color=options[_pos][2], end='\r')
                    next()
                    _pos += 1
                    printc(options[_pos][1], color=options[_pos][2] + [100], end='\r')
            def on_right():
                nonlocal _pos
                if not options[_pos][0] in choosen:
                    choosen.append(options[_pos][0])
                clear()
                printc(options[_pos][1], color=[1, 33, 100], end='\r')
                options[_pos] = options[_pos][0], options[_pos][1], [1, 33]
                next(len(options) - _pos)
                clear()
                printc('总数量: {} 预计大小: {} 已选择: {}'.format(sum(len(self.hot_update_list[key]['files']) for key in choosen), scale(sum(self.hot_update_list[key]['totalSize'] for key in choosen)), [key for key in choosen]), color=[1, 36], end='')
                back(len(options) - _pos)
            def on_left():
                nonlocal _pos
                if options[_pos][0] in choosen:
                    choosen.remove(options[_pos][0])
                clear()
                printc(options[_pos][1], color=[1, 34, 100], end='\r')
                options[_pos] = options[_pos][0], options[_pos][1], [1, 34]
                next(len(options) - _pos)
                clear()
                printc('总数量: {} 预计大小: {} 已选择: {}'.format(sum(len(self.hot_update_list[key]['files']) for key in choosen), scale(sum(self.hot_update_list[key]['totalSize'] for key in choosen)), [key for key in choosen]), color=[1, 36], end='')
                back(len(options) - _pos)
            keyboard.add_hotkey('up', on_up)
            keyboard.add_hotkey('down', on_down)
            keyboard.add_hotkey('right', on_right)
            keyboard.add_hotkey('left', on_left)
            back(len(options) + 1)
            printc(options[_pos][1], color=options[_pos][2] + [100], end='\r')
            keyboard.wait('esc')
            keyboard.clear_all_hotkeys()
            next(len(options) + 1 - _pos)
            clear()
            printc('开始下载', color=[1, 36])
            self.download_fromlist(choosen, savedir)
        else:
            printc('下载被取消', color=[1, 33])

    def download_fromlist(self, keys: list[str], savedir: str, threading_count: int = 6):
        _count = sum(len(self.hot_update_list[key]['files']) for key in keys)
        _lock = threading.Lock()
        _read = threading.Lock()
        _size = threading.Lock()
        _write = threading.Lock()
        per_path = str(Path(savedir) / 'persistent_res_list.json')
        if not (Path(savedir) / 'persistent_res_list.json').is_file():
            Path(savedir).mkdir(parents=True, exist_ok=True)
            with open(per_path, 'w') as f:
                f.write(r'{}')
                f.close()
            per = {}
        else:
            with open(per_path, 'r') as f:
                try:
                    per = json.loads(f.read())
                except:
                    with open(per_path, 'w') as f:
                        f.write(r'{}')
                        f.close()
                    per = {}
                f.close()
        files = dict()
        _unpack_count = 0
        for l in [self.hot_update_list[key]['files'] for key in keys]:
            for i in l:
                if (i in per):
                    if (per[i] == l[i]['md5']):
                        printc('{:<80}'.format('[{}]'.format(i)), '已经存在最新版本', color=[[36], [1, 32]])
                        _count -= 1
                        continue
                    else:
                        printc('[{}]将进行更新'.format(i), color=[1, 33])
                        _file_path: Path = Path(savedir) / i
                        if _file_path.is_file():
                            os.remove(str(_file_path))
                        if _file_path.with_name(_file_path.stem).is_dir():
                            os.removedirs(str(_file_path.with_name(_file_path.stem)))
                        files[i] = l[i]
                else:
                    files[i] = l[i]
        with tqdm(total=_count, desc='\033[1;33m总进度 已下载0B\033[m', unit='个', position=threading_count, leave=False) as pbar,\
             tqdm(total=_count, desc='\033[1;33m解压进度\033[m', unit='个', position=threading_count + 1, leave=False) as zipbar,\
             tqdm(total=_count, desc='\033[1;34m解包进度\033[m', unit='个', position=threading_count + 2, leave=False) as unpackbar:
            res_size = 0
            ts = time.time()

            def down(files, n):
                nonlocal _count, _unpack_count, res_size
                s = requests.Session()
                while(len(list(files.keys())) > 0):
                    _read.acquire()
                    file = random.choice(list(files.keys()))
                    md5 = files[file]['md5']
                    files.pop(file)
                    _read.release()
                    try:
                        stream = self.download_asset(file, s, lock=_lock, bar_position=n, thread_num=n)
                        _size.acquire()
                        res_size += len(stream)
                        _lock.acquire()
                        pbar.set_description('\033[1;33m总进度 已下载{} 平均速度{}\033[m'.format(scale(res_size), scale(res_size / (time.time() - ts)) + '/s'))
                        _lock.release()
                        _size.release()

                        def unzip(stream, name, md5, path):
                            nonlocal _unpack_count
                            with zipfile.ZipFile(file=BytesIO(stream)) as f:
                                del stream
                                f.extractall(path)
                            _write.acquire()
                            with open(per_path, 'r') as f:
                                per = json.loads(f.read())
                                f.close()
                            per[name] = md5
                            with open(per_path, 'w') as f:
                                f.write(json.dumps(per))
                                f.close()
                            _write.release()
                            _lock.acquire()
                            zipbar.update(1)
                            _lock.release()
                            
                            def unpack(file_path):
                                nonlocal _unpack_count
                                try:
                                    env = UnityPy.load(str(file_path))
                                    for obj in env.objects:
                                        data = obj.read()
                                        name = obj.type.name
                                        _p = file_path.with_name(file_path.stem)
                                        if name in ['Texture2D', 'Sprite']:
                                            _p.mkdir(parents=True, exist_ok=True)
                                            data.image.save(str(_p / (data.name + '.png')))
                                        elif name == 'TextAsset':
                                            _p.mkdir(parents=True, exist_ok=True)
                                            try:
                                                de = ArkAssets.text_asset_decrypt(data.script)
                                            except:
                                                de = data.script
                                            extension = '.txt'
                                            try:
                                                if bytes(de).decode()[0] == '{':
                                                    extension = '.json'
                                            except:
                                                pass
                                            with open(str(_p / (data.name + '.txt')), 'wb') as f:
                                                f.write(de)
                                                f.close()
                                        elif name == 'AudioClip':
                                            #continue #TODO
                                            for aname, adata in data.samples.items():
                                                _p.mkdir(parents=True, exist_ok=True)
                                                with open(str(_p / aname), "wb") as f:
                                                    f.write(adata)
                                                    f.close()
                                        elif name == 'Mesh':
                                            _p.mkdir(parents=True, exist_ok=True)
                                            with open(str(_p / (data.name + '.obj')), "wt", newline = "") as f:
                                                f.write(data.export())
                                                f.close()
                                        elif name == 'Font':
                                                if data.m_FontData:
                                                    extension = ".ttf"
                                                    if data.m_FontData[0:4] == b"OTTO":
                                                        extension = ".otf"
                                                    _p.mkdir(parents=True, exist_ok=True)
                                                    with open(str(_p / (data.name + extension)), "wb") as f:
                                                        f.write(data.m_FontData)
                                                        f.close()
                                except:
                                    pass
                                finally:
                                    _unpack_count += 1
                                    unpackbar.update(1)

                            threading.Thread(target=unpack, args=(Path(savedir) / name,)).start()
                        threading.Thread(target=unzip, args=(stream, file, md5, savedir), daemon=True).start()
                        del stream
                    except Exception as e:
                        _lock.acquire()
                        printc(e, color=[31])
                        _lock.release()
                    finally:
                        _lock.acquire()
                        pbar.update(1)
                        _lock.release()

            for i in range(threading_count):
                threading.Thread(target=down, args=(files, i), daemon=True).start()
            while(_unpack_count < _count):
                time.sleep(0.1)
            pbar.close()
            zipbar.close()
            unpackbar.close()

    def download_asset(self, path: str, session: requests.Session, bar_position: int = 0, lock: threading.Lock = None, thread_num: int = 0) -> bytes:
        global pos
        url = 'https://ak.hycdn.cn/assetbundle/{}/Android/assets/{}/{}'.format(
            'official' if self.server == ArkAssets.Servers.OFFICAL else 'bilibili',
            self.asset_version,
            re.sub('(?<=\.)((?!\.).)*$', 'dat', path).replace('/', '_').replace('#', '__'))
        headers = { "User-Agent": "BestHTTP" }
        if lock != None:
            lock.acquire()
        b = tqdm(unit_scale=True, desc='\033[33m线程{} [{}]:读取返回头中\033[m'.format(thread_num, path), unit='B', position=bar_position, leave=False)
        if lock != None:
            lock.release()
        req = session.get(url, stream=True, headers=headers)
        length = int(req.headers['content-length'])
        if lock != None:
            lock.acquire()
        b.close()
        pbar = tqdm(total=length, unit_scale=True, desc='\033[33m线程{} [{}]:下载中\033[m'.format(thread_num, path), unit='B', position=bar_position, leave=False)
        if lock != None:
            lock.release()
        res= bytes()
        st: float = time.time()
        chunk_size: int = length // 24
        if chunk_size <= 0:
            chunk_size = 1
        elif chunk_size >= 10485760:
            chunk_size = 10485760
        for chuck in req.iter_content(chunk_size=chunk_size):
            res += chuck
            if (len(res) != length):    
                if lock != None:
                    lock.acquire()
                pbar.update(len(chuck))
                pbar.refresh()
                if lock != None:
                    lock.release()
        st = time.time() - st
        if lock != None:
            lock.acquire()
        printc('{:<80}'.format('[{}]'.format(path)), '下载完毕  耗时{:.3f}s 平均速度{}'.format(st, scale(length / st) + '/s'),
            color=[[36], [1, 32]], log=tqdm.write)
        _per = length / 10485760
        if _per > 1:
            _per = 1
        printc('{:<16} {}'.format('dat包大小: ' + scale(length), int(_per * (os.get_terminal_size().columns - 33)) *'█'),
            color=[1, 34], log=tqdm.write)
        pbar.close()
        if lock != None:
            lock.release()
        return res

a = ArkAssets()
printc('输出路径：', color=[34], end='')
input = sys.stdin.readline().strip('\n')
a.download(input)