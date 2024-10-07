from flask import Flask, render_template, request, send_file, redirect, url_for
import cdsapi
import threading
import time
import logging
import os

app = Flask(__name__)

# 配置日志
logging.basicConfig(filename='era5_app.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def download_ecmwf_data(params):
    c = cdsapi.Client()
    try:
        dataset = "reanalysis-era5-pressure-levels"
        result = c.retrieve(dataset, params)
        filename = f"{params['pressure_level'][0]}_{params['year'][0]}_{params['month'][0]}_{params['day'][0]}.nc"
        result.download(filename)
        logging.info(f"数据下载成功: {params}")
        return filename
    except Exception as e:
        logging.error(f"API调用失败: {e}")
        print("API调用失败:", e)
        return None

def download_with_timeout(params):
    result = [None]
    def target():
        result[0] = download_ecmwf_data(params)
    
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=60)  # 60秒超时
    
    if thread.is_alive():
        logging.warning("下载超时")
        print("下载超时")
        return None
    return result[0]

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        product_type = request.form['product_type']
        variable = request.form.getlist('variable')
        pressure_level = request.form['pressure_level']
        year = request.form['year']
        month = request.form['month']
        day = request.form['day']
        time = request.form['time']
        geographical_area = request.form['geographical_area']

        if not variable:
            variable = ['geopotential']

        params = {
            'product_type': [product_type],
            'variable': variable,
            'pressure_level': [pressure_level],
            'year': [year],
            'month': [month],
            'day': [day],
            'time': [time],
            'data_format': 'netcdf',
            'download_format': 'unarchived'
        }

        if geographical_area == 'whole_available_region':
            params.pop('geographical_area', None)
        else:
            north = request.form['north']
            west = request.form['west']
            south = request.form['south']
            east = request.form['east']
            params['area'] = [float(north), float(west), float(south), float(east)]

        logging.info(f"开始下载数据: {params}")
        downloaded_file = download_with_timeout(params)

        if downloaded_file is None:
            logging.error("下载失败")
            return redirect(url_for('error'))

        logging.info(f"数据下载完成: {params}")
        print("参数:", params)

        return send_file(downloaded_file, as_attachment=True)

    return render_template('index.html')

@app.route('/error')
def error():
    logging.error("访问错误页面")
    return render_template('error.html'), 502

if __name__ == '__main__':
    logging.info("应用程序启动")
    app.run(debug=False, host='0.0.0.0')
