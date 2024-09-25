from flask import Flask, render_template, request, send_file, redirect, url_for
import cdsapi

app = Flask(__name__)

def download_ecmwf_data(params):
    c = cdsapi.Client()
    try:
        dataset = "reanalysis-era5-pressure-levels"
        result = c.retrieve(dataset, params)
        result.download('download.nc')  # 将下载的文件保存为 download.nc
        return 'download.nc'
    except Exception as e:
        print("API call failed:", e)
        # 如果API调用失败，返回None
        return None

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
            variable = ['geopotential']  # 设置默认变量

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

        # 如果选择了整个可用区域，则删除地理区域参数
        if geographical_area == 'whole_available_region':
            params.pop('geographical_area', None)
        else:
            north = request.form['north']
            west = request.form['west']
            south = request.form['south']
            east = request.form['east']
            params['area'] = [float(north), float(west), float(south), float(east)]

        # 使用构建的参数调用Copernicus API下载数据
        downloaded_file = download_ecmwf_data(params)

        if downloaded_file is None:
            # 如果结果为None，说明API调用失败，重定向到失败页面
            return redirect(url_for('error'))

        # 打印参数，用于确认参数是否正确
        print("Params:", params)

        # 将下载完成的文件发送给客户端
        return send_file(downloaded_file, as_attachment=True)

    return render_template('index.html')

@app.route('/error')
def error():
    # 渲染一个错误页面
    return render_template('error.html'), 500

if __name__ == '__main__':
    app.run(debug=True)
