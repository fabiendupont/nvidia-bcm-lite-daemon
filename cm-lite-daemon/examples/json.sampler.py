#!/usr/bin/env python3

import json
import random
import sys


def initialize():
    metricA = {"metric": "lite.metric.A", "class": "Test/lite"}
    metricB = {"metric": "lite.metric.B", "class": "Test/lite"}
    metricC = {"metric": "lite.metric.C", "class": "Test/lite"}
    enumK = {"metric": "lite.enum.K", "class": "Test/lite", "enum": ["no", "yes"]}
    enumL = {
        "metric": "lite.enum.L",
        "class": "Test/lite",
        "enum": {"Hello world": 11, "Dude": 4},
    }
    checkX = {"check": "lite.check.X", "class": "Test/lite"}
    checkY = {"check": "lite.check.Y", "class": "Test/lite"}
    checkZ = {"check": "lite.check.Z", "class": "Test/lite"}
    return [metricA, metricB, metricC, enumK, enumL, checkX, checkY, checkZ]


def sample():
    metricA = {"metric": "lite.metric.A", "value": 1}
    metricB = {"metric": "lite.metric.B", "value": random.randint(1, 2)}
    metricC = {"metric": "lite.metric.C", "value": random.uniform(0, 9)}
    enumK = {"metric": "lite.enum.K", "value": "yes"}
    enumL = {"metric": "lite.enum.L", "value": "Hello world"}
    checkX = {"check": "lite.check.X", "value": "PASS"}
    checkY = {
        "check": "lite.check.Y",
        "value": "FAIL",
        "info": "A long\nmultilined text\nfor testing\n",
    }
    checkZ = {"check": "lite.check.Z", "value": "UNKNOWN"}
    return [metricA, metricB, metricC, enumK, enumL, checkX, checkY, checkZ]


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--initialize":
        data = initialize()
    else:
        data = sample()
    print((json.dumps(data, indent=4)))


if __name__ == "__main__":
    main()
