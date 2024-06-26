"""
This file is for running simulations to study how accuracy and EDP 
changes with dim/arrayCol
"""

from pathlib import Path
import os
import pandas as pd
import numpy as np
import yaml
from typing import Tuple
import re
import plotly.express as px
import plotly.graph_objects as go
import multiprocessing

scriptFolder = Path(__file__).parent
templateConfigPath = scriptFolder.joinpath("try_var_settings.yml")
simOutputBaseDir = scriptFolder.parent.joinpath("outputs")
pyScriptPath = scriptFolder.parent.joinpath("driver.py")
emailScriptPath = scriptFolder.joinpath("sendEmail.py")
resultDir = scriptFolder.joinpath("results")
configDir = scriptFolder.parent.joinpath("configs")
if not resultDir.exists():
    resultDir.mkdir(parents=True)
plotlyOutputPath = scriptFolder.joinpath("./plot.html")
matplotlibOutputPath = scriptFolder.joinpath("./plot.png")

varList = [
    0,
    # 0.00001,
    # 0.00003,
    # 0.00005,
    # 0.00007,
    # 0.0001,
    # 0.0003,
    0.0005,
    0.0007,
    0.001,
    0.003,
    0.005,
    0.007,
    0.01,
    0.03,
    0.05,
    0.07,
    0.08,
    0.1,
    0.11,
    0.12,
    0.15,
    0.20,
    0.30,
    0.5,
    1.0
]
sampleTimesList = [100]

scalingFactor = 2

jobList = {
    "300train100validation": {
        "n_train": 300,
        "n_validation": 100,
        "hasWeightVar": True,
        "outputDir": simOutputBaseDir.joinpath("300train100validation"),
    },
    # "30train10validation": {
    #     "n_train": 30,
    #     "n_validation": 10,
    #     'hasWeightVar': True,
    #     "outputDir": simOutputBaseDir.joinpath("30train10validation"),
    # },
}


def getAccu(outputDir: Path, accuracyResult: pd.DataFrame) -> pd.DataFrame:
    """
    return: accuracy, EDP
    """
    # print(accuracyResult)
    logList = list(outputDir.glob("*.log"))
    for logPath in logList:
        accuracy = None
        with open(logPath, mode="r") as f:
            for lineID, line in enumerate(f):
                if re.search(r"Final Tree with accuracy", line):
                    accuracy = float(re.search("[0-9]+.[0-9]+", line).group())

        assert accuracy != None, "accuracy or edp not extracted!"

        fileStem = logPath.stem
        stemTokens = fileStem.strip().split("_")
        stdDev = float(re.match("[0-9]+.[0-9]+", stemTokens[0]).group())
        sampleTimes = int(re.match("[0-9]+", stemTokens[1]).group())
        # print(f'stdDev: {stdDev}, sampleTimes: {sampleTimes}')

        accuracyResult.at[stdDev, sampleTimes] = accuracy
    # print(accuracyResult)
    return accuracyResult


def run_exp(
    accuResult: pd.DataFrame, outputDir: Path, n_train: int, n_validation: int
) -> pd.DataFrame:
    settingsList = []
    for sampleTimes in sampleTimesList:
        for stdDev in varList:
            # print("*" * 30)
            # print(f"stdDev = {stdDev}, sampleTime = {sampleTimes}")

            with open(templateConfigPath, mode="r") as fin:
                config = yaml.load(fin, Loader=yaml.FullLoader)

            config["weightVar"]["stdDev"] = stdDev * scalingFactor
            config["weightVar"]["sampleTimes"] = sampleTimes

            destConfigPath = configDir.joinpath(
                "%fstdDev_%dsampleTimes.yml" % (stdDev, sampleTimes)
            )
            with open(destConfigPath, "w") as yaml_file:
                yaml.dump(config, yaml_file, default_flow_style=False)

            runOutputPath = outputDir.joinpath(
                "%fstdDev_%dsampleTimes_runOutput.log" % (stdDev, sampleTimes)
            )
            treeTextOutputPath = outputDir.joinpath(
                "%fstdDev_%dsampleTimes_treeText.txt" % (stdDev, sampleTimes)
            )
            settingsList.append(
                {
                    "n_train": n_train,
                    "n_validation": n_validation,
                    "configPath": destConfigPath,
                    "runOutputPath": runOutputPath,
                    "treeTextOutputPath": treeTextOutputPath,
                }
            )

    # num_processes = multiprocessing.cpu_count()
    num_processes = 1

    with multiprocessing.Pool(num_processes) as pool:
        pool.map(runner, settingsList)

    # for settings in settingsList:
    #     runner(settings)

    accuResult = getAccu(outputDir, accuResult)

    return accuResult


def runner(config: dict):
    n_train, n_validation, configPath, runOutputPath, treeTextOutputPath = (
        config["n_train"],
        config["n_validation"],
        config["configPath"],
        config["runOutputPath"],
        config["treeTextOutputPath"],
    )

    assert pyScriptPath.exists(), "The script to be run does not exist!"
    assert (
        os.system(
            f"/home/andyliu/miniconda3/envs/hd-mann/bin/python {pyScriptPath} --n_train {n_train} --n_validation {n_validation} --output_path {treeTextOutputPath} --config {configPath} | tee {runOutputPath}"
        )
        == 0
    ), "run script failed."
    print(f"finished running with config {configPath}")


def main():
    for jobName in jobList.keys():
        print("**************************************************")
        print(f"               job: {jobName}")
        print("**************************************************")
        jobList[jobName]["accuResult"] = pd.DataFrame(
            np.zeros((len(varList), len(sampleTimesList)), dtype=float),
            index=varList,
            columns=sampleTimesList,
        )

        if not jobList[jobName]["outputDir"].exists():
            jobList[jobName]["outputDir"].mkdir(parents=True)

        jobList[jobName]["accuResult"] = run_exp(
            jobList[jobName]["accuResult"],
            jobList[jobName]["outputDir"],
            jobList[jobName]["n_train"],
            jobList[jobName]["n_validation"],
        )

        jobList[jobName]["accuResult"].to_csv(
            jobList[jobName]["outputDir"].joinpath("accuracy.csv")
        )
        print("saved stat")

    # plotly_plot(jobList)
    # matplotlib_plot(jobList)
    os.system(
        f'/home/andyliu/miniconda3/envs/hd-mann/bin/python {emailScriptPath} -m "Finished script: try_var_settings"'
    )


def plot_jobs():
    for jobName in jobList:
        jobList[jobName]["accuResult"] = pd.read_csv(
            jobList[jobName]["accuResultPath"], index_col=0
        )
        jobList[jobName]["accuResult"].columns = [
            float(i) for i in jobList[jobName]["accuResult"].columns
        ]
        jobList[jobName]["edpResult"] = pd.read_csv(
            jobList[jobName]["edpResultPath"], index_col=0
        )
        jobList[jobName]["edpResult"].columns = [
            float(i) for i in jobList[jobName]["edpResult"].columns
        ]

    # plotly_plot(jobList)


if __name__ == "__main__":
    main()
    # plot_jobs()
