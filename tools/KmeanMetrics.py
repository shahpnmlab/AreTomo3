#!/usr/bin/python

import pandas as pd
import numpy as np
import torch
from torch_kmeans import KMeans
import argparse
import math
import sys

class ReadMetricsCsv:
    def __init__(self):
        self.dataFrame = None
        self.numRows = 0
        self.numCols = 0

    def doIt(self, csvFile):
        print("Processing: " + csvFile + "\n")
        self.dataFrame = pd.read_csv(csvFile, engine='python')
        #------------------
        self.numRows = len(self.dataFrame)
        if self.numRows == 0:
            print("...... No data found!")
            return

    def getColumn(self, iCol):
        if self.numRows == 0:
            return None
        keys = self.dataFrame.columns
        return self.dataFrame[keys[iCol]].values

    def getMrcFileNames(self):
        return self.getColumn(0)

    def getThickness(self):
        return self.getColumn(1)

    def getTiltAxis(self):
        return self.getColumn(2)

    def getGlobalShift(self):
        return self.getColumn(3)

    def getBadPatchLow(self):
        return self.getColumn(4)
    
    def getBadPatchAll(self):
        return self.getColumn(5)

    def getCtfRes(self):
        return self.getColumn(6)

    def getCtfScore(self):
        return self.getColumn(7)

    def getPixSize(self):
        return self.getColumn(8)

    def getValArray(self):
        valArr = self.dataFrame.to_numpy()
        iColEnd = valArr.shape[1] - 1
        return valArr[0:, 1:iColEnd]


class KmeanCluster:
    def __init__(self):
        self.metrics = None

    def generate(self, metricsArr, iNumClasses):
        self.metrics = metricsArr
        iNumCols = self.metrics.shape[1]
        #--------------------------------------------
        # normalization per column by mean and sigma
        #--------------------------------------------
        for i in range(iNumCols):
            col = self.metrics[:, i]
            mean = np.mean(col)
            std = np.std(col) + 1e-30
            col -= mean # in-place subtraction
            col /= std  # in-place division
        #------------------------------------
        # normalization per row by magnitude
        #------------------------------------
        iNumRows = self.metrics.shape[0]
        for i in range(iNumRows):
            row = self.metrics[i, :]
            row /= (np.linalg.norm(row) + 1e-30)
        #----------------------------------------------
        # expand the metrics to 3D array as required
        # by KMeans module.
        #----------------------------------------------
        metrics3D = np.expand_dims(self.metrics, axis=0)
        #---------------------------------------------------
        # change the data type from np_object to np.float32
        # since data frame contains string MRC files
        #---------------------------------------------------
        metrics3D = list(metrics3D)
        metrics3D = np.array(metrics3D, dtype=np.float32)
        metrics3D = torch.from_numpy(metrics3D)
        #------------------------
        # conduct kmean analysis
        #------------------------
        model = KMeans(n_clusters = iNumClasses)
        result = model(metrics3D)
        labels = result.labels[0]
        #------------------------
        clusterSizes = np.zeros(iNumClasses)
        for i in range(len(labels)):
            for j in range(iNumClasses):
                if labels[i] == j:
                    clusterSizes[j] += 1
        print("\nCluster sizes: " + str(clusterSizes) + "\n")
        return labels


class WriteLabelCsv:
    def __init__(self):
        pass

    def doIt(self, csvFile, mrcFileNames, labels):
        mrcList = mrcFileNames.tolist()
        labList = labels.tolist()
        mrcLabList = list(zip(mrcList, labList))
        df = pd.DataFrame(mrcLabList, columns=['Tilt_Series', 'Class']);
        df.to_csv(csvFile, index=False)
        print("Labels have been saved in: " + csvFile + "\n")


def main():
    parser = argparse.ArgumentParser(formatter_class= \
        argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--in_csv", "-ic", type=str, default=None, \
        help="CSV metrics file generated by AreTomo3")
    parser.add_argument("--num_classes", "-nc", type=int, default=3, \
        help="number of kmean classes")
    parser.add_argument("--out_csv", "-oc", type=str, default=None, \
        help="Output CSV file for saving classes")
    args = parser.parse_args()
    #---------------
    print("\nInput metrics file: " + args.in_csv)
    print("Number of classes:   " + str(args.num_classes));
    print("Output label file:   " + args.out_csv + "\n");
    #---------------
    readMetricsCsv = ReadMetricsCsv()
    readMetricsCsv.doIt(args.in_csv)
    #---------------
    mrcFileNames = readMetricsCsv.getMrcFileNames()
    valArr = readMetricsCsv.getValArray()
    #---------------
    kMeanCluster = KmeanCluster()
    labels = kMeanCluster.generate(valArr, args.num_classes)
    #---------------
    writeLabelCsv = WriteLabelCsv()
    writeLabelCsv.doIt(args.out_csv, mrcFileNames, labels)

if __name__ == "__main__":
    main()


