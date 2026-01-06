// webpack.config.js

const path = require('path');

module.exports = {
  mode: 'development',
  entry: {
    main: './src/main/main.ts',
    preload: './src/main/preload.ts',
  },
  target: 'electron-main',
  output: {
    path: path.resolve(__dirname, 'dist/main'),
    filename: '[name].js',
  },
  module: {
    rules: [
      {
        test: /\.ts$/,
        use: {
          loader: 'ts-loader',
          options: {
            configFile: 'tsconfig.main.json'
          }
        },
        exclude: /node_modules/,
      },
    ],
  },
  resolve: {
    extensions: ['.ts', '.js'],
  },
  node: {
    __dirname: false,
    __filename: false,
  },
};