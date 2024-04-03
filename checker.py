import asyncio
import concurrent
import json
import os
import uuid
import requests
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

# 设置允许上传的文件类型
ALLOWED_EXTENSIONS = {'xbs'}

# 初始化全局变量
# 是否完成
is_done = False
update_xbs_path = ''
xbs_check_result = {}
# 待删除的文件
to_delete_files = []

def xbs2json(xbs_path):
    global to_delete_files
    out_path = os.path.join(app.config["JSON"],str(uuid.uuid4())+'.json')
    to_delete_files.append(out_path)
    cmd = f'./xbsrebuild xbs2json -i {xbs_path} -o {out_path}'
    os.system(cmd)
    if not os.path.exists(out_path):
        print('xbsrebuild failed')
        exit(0)
    else:
        return out_path

def json2xbs(json_path):
    out_path = os.path.join(app.config["UPDATE_XBS"],str(uuid.uuid4())+'.xbs')
    cmd = f'./xbsrebuild json2xbs -i {json_path} -o {out_path}'
    os.system(cmd)
    if not os.path.exists(out_path):
        print('xbsrebuild failed')
        exit(0)
    else:
        return out_path






# 定义允许上传文件的函数
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS




# xbs检测项目,host,搜索，章节，内容，分类
def check_host(req_obj):
    try:
        with requests.get(req_obj, timeout=5) as response:
            return response.status_code == 200
    except Exception as e:
        return False
def check_search(req_obj):

    return False
def check_chapter(req_obj):

    return False
def check_content(req_obj):

    return False

def check_category(req_obj):

    return False

def checker(ws):
    global xbs_check_result
    # 构建搜索请求,首先检测host,如果不可用，则返回false，否则继续检测搜索，如果没有搜索则检测分类。
    xbs_obj = ws[0]
    work_path = ws[1]
    xbs_host = xbs_obj["sourceUrl"]
    tmp = check_host(xbs_host)
    xbs_obj["enable"] = tmp
    if tmp:
        xbs_check_result[xbs_obj["sourceName"]] = '可用'
    else:
        xbs_check_result[xbs_obj["sourceName"]] = '不可用'

    return xbs_obj
    # json_name = os.path.join(work_path, f"{xbs_obj['sourceName']}.json")
    # with open(json_name, 'w', encoding='utf-8') as f:
    #     json.dump(xbs_obj, f, ensure_ascii=False, indent=4)



async def update_file(result):
    global is_done,update_xbs_path,to_delete_files
    f_name = str(uuid.uuid4())
    json_path = os.path.join(app.config['UPDATE_XBS'], f_name+".json")
    to_delete_files.append(json_path)
    tmp = {}
    for i in result:
        tmp[i['sourceName']] = i
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(tmp, f, ensure_ascii=False, indent=4)
    update_xbs_path = json2xbs(json_path)
    is_done = (update_xbs_path != '')
    for i in to_delete_files:
        print(i)
        os.remove(i)
    to_delete_files.clear()





async def worker(works,work_path):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(executor, checker, (w,work_path)) for w in works]
        result = await asyncio.gather(*tasks)
        await update_file(result)




def run_work(xbs_path):
    #     xbs转json
    out_path = xbs2json(xbs_path)
    # 取out_path的目录
    # work_path = os.path.join(os.path.dirname(out_path),os.path.basename(out_path).split('.')[0])
    # os.makedirs(work_path, exist_ok=True)
    work_path = ''
    with open(out_path, 'r') as f:
        jsonData = json.loads(f.read())
    keys = jsonData.keys()
    works = []
    for key in keys:
        obj = jsonData[key]
        works.append(obj)
    # 异步处理文件内容，检测其中的 URL 可用性
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(worker(works,work_path))
    loop.close()

# 定义首页路由,上传文件
@app.route('/', methods=['GET', 'POST'])
def index():
    global xbs_path,is_done,to_delete_files
    is_done = False
    if request.method == 'POST':
        file = request.files['file']
        # 保存文件到uploads文件夹,重命名xbs
        if file and allowed_file(file.filename):
            filename = str(uuid.uuid4())+".xbs"
            print(app.config['XBS'])
            xbs_path = os.path.join(app.config['XBS'], filename)
            to_delete_files.append(xbs_path)
            file.save(xbs_path)
            run_work(xbs_path)
            return jsonify({'redirect': request.url})
    return render_template('index.html')
@app.route('/download', methods=['GET'])
def download_file():
    global update_xbs_path
    return send_file(update_xbs_path, as_attachment=True)
# 刷新结果
@app.route('/refresh', methods=['GET'])
def refresh_result():
    global is_done,xbs_check_result
    if is_done:
        # 构建更新后xbs下载链接
        return jsonify({'status': 'finished', 'message': '完成','xbs_check_result':xbs_check_result})
    else:
        return jsonify({'status': 'running', 'message': '尚未完成','xbs_check_result':xbs_check_result})

# 启动Flask应用
if __name__ == '__main__':
    app.config['WORKER'] = 'worker'
    app.config['UPDATE_XBS'] = 'worker/update_xbs'
    app.config['XBS'] = 'worker/xbs'
    app.config['JSON'] = 'worker/json'
    os.makedirs(app.config['WORKER'], exist_ok=True)
    os.makedirs(app.config['XBS'], exist_ok=True)
    os.makedirs(app.config['UPDATE_XBS'], exist_ok=True)
    os.makedirs(app.config['JSON'], exist_ok=True)
    app.run(host='0.0.0.0', port=9797)

