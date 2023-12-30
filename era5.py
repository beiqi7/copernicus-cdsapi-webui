from flask import Flask, render_template, request, send_file
import cdsapi

app = Flask(__name__)

# Copernicus API配置，包括API key
def download_ecmwf_data(params):
    c = cdsapi.Client()

    result = c.retrieve(
        'reanalysis-era5-pressure-levels',
        params,
        'download.nc'
    )
    return result

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

        # 根据用户的选择构建API请求参数
        params = {
            'product_type': product_type,
            'variable': variable,
            'pressure_level': pressure_level,
            'year': year,
            'month': month,
            'day': day,
            'time': time
            # 添加其他参数
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
        result = download_ecmwf_data(params)

        # 打印参数，用于确认参数是否正确
        print("Params:", params)

        # 将下载完成的文件发送给客户端
        return send_file('download.nc', as_attachment=True)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
