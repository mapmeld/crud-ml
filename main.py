import sys, os, json, shutil, time, traceback

from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename

import pandas as pd
from sklearn.naive_bayes import BernoulliNB as bnb
from sklearn.externals import joblib
import numpy as np

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = './uploads'
ALLOWED_EXTENSIONS = {'txt', 'csv'}

# inputs
training_data = 'data/titanic.csv'
include = ['Age', 'Sex', 'Embarked', 'Survived']
dependent_variable = include[-1]

model_directory = 'model'
model_file_name = '%s/model.pkl' % model_directory
model_columns_file_name = '%s/model_columns.pkl' % model_directory

# These will be populated at training time
model_columns = None
clf = None


@app.route('/predict', methods=['POST'])
def predict():
    if clf:
        try:
            json_ = request.json
            query = pd.get_dummies(pd.DataFrame(json_))

            # https://github.com/amirziai/sklearnflask/issues/3
            # Thanks to @lorenzori
            query = query.reindex(columns=model_columns, fill_value=0)

            prediction = list(clf.predict(query))

            # Converting to int from int64
            return jsonify({"prediction": list(map(int, prediction))})

        except Exception as e:

            return jsonify({'error': str(e), 'trace': traceback.format_exc()})
    else:
        print('train first')
        return 'no model here'

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/train/create', methods=['POST'])
def create_train():
    if 'file' not in request.files:
        return 'no file included in POST'
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    else:
        return 'need CSV file for upload'

    df = pd.read_csv(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    df_ = df[include]

    categoricals = []  # going to one-hot encode categorical variables

    for col, col_type in df_.dtypes.items():
        if col_type == 'O':
            categoricals.append(col)
        else:
            df_[col].fillna(0, inplace=True)  # fill NA's with 0 for ints/floats, too generic

    # get_dummies effectively creates one-hot encoded variables
    df_ohe = pd.get_dummies(df_, columns=categoricals, dummy_na=True)

    x = df_ohe[df_ohe.columns.difference([dependent_variable])]
    y = df_ohe[dependent_variable]

    # capture a list of columns that will be used for prediction
    global model_columns
    model_columns = list(x.columns)
    joblib.dump(model_columns, model_columns_file_name)

    global clf
    clf = bnb()
    start = time.time()
    clf.partial_fit(x, y, classes=np.unique(y))

    joblib.dump(clf, model_file_name)

    message1 = 'Trained in %.5f seconds' % (time.time() - start)
    message2 = 'Model training score: %s' % clf.score(x, y)
    return_message = 'Success. \n{0}. \n{1}.'.format(message1, message2)
    return return_message

@app.route('/train/insert', methods=['POST'])
def insert_train():
    if clf:
        if 'file' not in request.files:
            return 'no file included in POST'
        file = request.files['file']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            return 'need CSV file for upload'

        df = pd.read_csv(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        df_ = df[include]

        categoricals = []  # going to one-hot encode categorical variables

        for col, col_type in df_.dtypes.items():
            if col_type == 'O':
                categoricals.append(col)
            else:
                df_[col].fillna(0, inplace=True)  # fill NA's with 0 for ints/floats, too generic

        # get_dummies effectively creates one-hot encoded variables
        df_ohe = pd.get_dummies(df_, columns=categoricals, dummy_na=True)

        x = df_ohe[df_ohe.columns.difference([dependent_variable])]
        y = df_ohe[dependent_variable]

        clf.partial_fit(x, y)
        joblib.dump(clf, model_file_name)
        return 'Success\nModel training score: %s' % clf.score(x, y)
    else:
        print('train first')
        return 'no model here'

@app.route('/train/delete', methods=['GET'])
def delete_train():
    try:
        shutil.rmtree('model')
        os.makedirs(model_directory)
        return 'Model wiped'

    except Exception as e:
        print(str(e))
        return 'Could not remove and recreate the model directory'


if __name__ == '__main__':
    try:
        port = int(sys.argv[1])
    except Exception as e:
        port = 8080

    try:
        clf = joblib.load(model_file_name)
        print('model loaded')
        model_columns = joblib.load(model_columns_file_name)
        print('model columns loaded')

    except Exception as e:
        print('No model here')
        print('Train first')
        print(str(e))
        clf = None

    app.run(host='0.0.0.0', port=port, debug=True)
