const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// 🚨 Windows fix: completely disable Node externals (node:sea)
config.resolver.unstable_enablePackageExports = false;
config.resolver.unstable_conditionNames = [];
config.resolver.extraNodeModules = {};

module.exports = config;
