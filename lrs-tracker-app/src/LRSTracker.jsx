import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  AlertCircle,
} from "lucide-react";

const LRSTracker = () => {
  const [qqqData, setQqqData] = useState([]);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [sma200, setSma200] = useState(null);
  const [signal, setSignal] = useState("TQQQ"); // Current position
  const [alertMessage, setAlertMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [performanceData, setPerformanceData] = useState([]);

  const BUFFER = 0.005; // 0.5% buffer

  useEffect(() => {
    fetchQQQData();
  }, []);

  const fetchQQQData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Using Alpha Vantage API - free tier allows 25 requests per day
      // Users can get their own free API key at https://www.alphavantage.co/support/#api-key
      const API_KEY = "M2OL6LSQ4OZBRFEE"; // Replace with your own key for production use

      const handleResponse = (json, label) => {
        if (json.Note || json.Information) {
          throw new Error(
            json.Note || json.Information,
          );
        }
        if (!json["Time Series (Daily)"]) {
          throw new Error(
            `Invalid ${label} response from Alpha Vantage. Please try again.`,
          );
        }
      };

      // Free tier: 1 request per second, so fetch sequentially with delays
      const delay = (ms) => new Promise((r) => setTimeout(r, ms));

      const qqqResponse = await fetch(
        `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=QQQ&outputsize=compact&apikey=${API_KEY}`,
      );
      const qqqJson = await qqqResponse.json();
      handleResponse(qqqJson, "QQQ");

      await delay(1200);

      const tqqqResponse = await fetch(
        `https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=TQQQ&outputsize=compact&apikey=${API_KEY}`,
      );
      const tqqqJson = await tqqqResponse.json();
      handleResponse(tqqqJson, "TQQQ");

      await delay(1200);

      const smaResponse = await fetch(
        `https://www.alphavantage.co/query?function=SMA&symbol=QQQ&interval=daily&time_period=200&series_type=close&apikey=${API_KEY}`,
      );
      const smaJson = await smaResponse.json();
      if (smaJson.Note || smaJson.Information) {
        throw new Error(smaJson.Note || smaJson.Information);
      }

      // Parse QQQ data
      const qqqTimeSeries = qqqJson["Time Series (Daily)"];
      const qqqPrices = Object.entries(qqqTimeSeries)
        .map(([date, values]) => ({
          date,
          close: parseFloat(values["4. close"]),
        }))
        .sort((a, b) => new Date(a.date) - new Date(b.date));

      // Parse TQQQ data
      const tqqqTimeSeries = tqqqJson["Time Series (Daily)"];
      const tqqqPrices = Object.entries(tqqqTimeSeries)
        .map(([date, values]) => ({
          date,
          close: parseFloat(values["4. close"]),
        }))
        .sort((a, b) => new Date(a.date) - new Date(b.date));

      // Parse SMA data into a map for easy lookup
      const smaData = smaJson["Technical Analysis: SMA"] || {};
      const smaMap = new Map(
        Object.entries(smaData).map(([date, v]) => [date, parseFloat(v.SMA)]),
      );

      if (qqqPrices.length === 0) {
        throw new Error("No QQQ data available");
      }

      // Get the most recent trading day
      const mostRecentDate = qqqPrices[qqqPrices.length - 1].date;
      setLastUpdate(mostRecentDate);

      setQqqData(qqqPrices);
      calculateSignal(qqqPrices, smaMap);
      calculatePerformance(qqqPrices, tqqqPrices, smaMap);

      setLoading(false);
    } catch (error) {
      console.error("Error fetching data:", error);
      setError(
        error.message || "Failed to load market data. Please try again.",
      );
      setLoading(false);
    }
  };

  const parseCSV = (csvText) => {
    const lines = csvText.trim().split("\n");
    const data = [];

    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(",");
      if (values.length >= 5 && values[4] !== "null") {
        data.push({
          date: values[0],
          close: parseFloat(values[4]),
        });
      }
    }

    return data;
  };

  const calculateSMA = (data, period) => {
    if (data.length < period) return null;
    const recentPrices = data.slice(-period);
    const sum = recentPrices.reduce((acc, item) => acc + item.close, 0);
    return sum / period;
  };

  const calculateSignal = (prices, smaMap) => {
    const latest = prices[prices.length - 1];
    const sma = smaMap.get(latest.date);

    if (!sma) return;

    setCurrentPrice(latest.close);
    setSma200(sma);

    const percentDiff = (latest.close - sma) / sma;

    let newSignal = signal;
    let alert = "";

    if (percentDiff >= BUFFER) {
      // Price is 0.5% or more above SMA
      if (signal === "CASH") {
        newSignal = "TQQQ";
        alert = "🚨 BUY SIGNAL: Switch from CASH to TQQQ!";
      } else {
        newSignal = "TQQQ";
      }
    } else if (percentDiff <= -BUFFER) {
      // Price is 0.5% or more below SMA
      if (signal === "TQQQ") {
        newSignal = "CASH";
        alert = "🚨 SELL SIGNAL: Switch from TQQQ to CASH!";
      } else {
        newSignal = "CASH";
      }
    }
    // If within buffer zone, maintain current position

    setSignal(newSignal);
    if (alert) setAlertMessage(alert);
  };

  const calculatePerformance = (qqqPrices, tqqqPrices, smaMap) => {
    // Create maps for easy lookup
    const tqqqDates = new Set(tqqqPrices.map((p) => p.date));
    const qqqMap = new Map(qqqPrices.map((p) => [p.date, p.close]));
    const tqqqMap = new Map(tqqqPrices.map((p) => [p.date, p.close]));

    // Get dates that exist in both QQQ and TQQQ datasets and have SMA data
    const simDates = qqqPrices
      .filter((p) => tqqqDates.has(p.date) && smaMap.has(p.date))
      .map((p) => p.date)
      .sort();

    if (simDates.length < 2) {
      setPerformanceData([]);
      return;
    }

    let lrsValue = 10000; // Starting with $10k
    let lrsShares = 0;
    let cashPosition = 10000;
    let qqqBHValue = 10000;
    let qqqBHShares = 10000 / qqqMap.get(simDates[0]);
    let spyValue = 10000; // Approximation
    let inTQQQ = false; // Start in cash

    const performance = simDates.map((date, idx) => {
      const qqqPrice = qqqMap.get(date);
      const tqqqPrice = tqqqMap.get(date);

      if (idx === 0) {
        return {
          date: date,
          lrs: lrsValue,
          qqq: qqqBHValue,
          spy: spyValue,
        };
      }

      const sma = smaMap.get(date);
      const percentDiff = (qqqPrice - sma) / sma;

      // Check for signal changes with hysteresis
      if (percentDiff >= BUFFER && !inTQQQ) {
        inTQQQ = true;
        lrsShares = cashPosition / tqqqPrice;
        cashPosition = 0;
      } else if (percentDiff <= -BUFFER && inTQQQ) {
        inTQQQ = false;
        cashPosition = lrsShares * tqqqPrice;
        lrsShares = 0;
      }

      // Calculate LRS value
      if (inTQQQ) {
        lrsValue = lrsShares * tqqqPrice;
      } else {
        lrsValue = cashPosition;
      }

      // Calculate buy & hold QQQ value
      qqqBHValue = qqqBHShares * qqqPrice;

      // Calculate approximate SPY (assuming 95% correlation with QQQ)
      const qqqReturn =
        (qqqPrice - qqqMap.get(simDates[idx - 1])) /
        qqqMap.get(simDates[idx - 1]);
      spyValue *= 1 + qqqReturn * 0.95;

      // Add monthly contribution on the 1st of each month
      const currentDate = new Date(date);
      const prevDate = new Date(simDates[idx - 1]);

      if (currentDate.getMonth() !== prevDate.getMonth() || idx === 1) {
        const monthlyContribution = 2000;

        if (inTQQQ) {
          lrsShares += monthlyContribution / tqqqPrice;
        } else {
          cashPosition += monthlyContribution;
        }

        qqqBHShares += monthlyContribution / qqqPrice;
        spyValue += monthlyContribution;
      }

      return {
        date: date,
        lrs: Math.round(lrsValue),
        qqq: Math.round(qqqBHValue),
        spy: Math.round(spyValue),
      };
    });

    setPerformanceData(performance);
  };

  const getStatusColor = () => {
    if (signal === "TQQQ") return "text-green-600";
    if (signal === "CASH") return "text-red-600";
    return "text-yellow-600";
  };

  const getStatusIcon = () => {
    if (signal === "TQQQ") return <TrendingUp className="w-8 h-8" />;
    if (signal === "CASH") return <TrendingDown className="w-8 h-8" />;
    return <DollarSign className="w-8 h-8" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="text-xl mb-4">Loading market data...</div>
          <div className="text-sm text-gray-500">
            This may take a few seconds
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="max-w-md bg-white rounded-lg shadow-lg p-8">
          <div className="text-red-600 text-xl font-semibold mb-4">
            ⚠️ Error Loading Data
          </div>
          <p className="text-gray-700 mb-4">{error}</p>

          {error.includes("API") && (
            <div className="mb-4 p-3 bg-blue-50 rounded text-sm text-gray-700">
              <p className="font-semibold mb-2">💡 To fix this:</p>
              <ol className="list-decimal ml-4 space-y-1">
                <li>
                  Get a free API key at{" "}
                  <a
                    href="https://www.alphavantage.co/support/#api-key"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 underline"
                  >
                    alphavantage.co
                  </a>
                </li>
                <li>Replace 'demo' with your key in the code (line ~30)</li>
                <li>Free tier: 25 requests/day (plenty for daily checks!)</li>
              </ol>
            </div>
          )}

          <button
            onClick={fetchQQQData}
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const percentFromSMA = sma200
    ? (((currentPrice - sma200) / sma200) * 100).toFixed(2)
    : 0;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-gray-800">
            Leverage Rotation Strategy Tracker
          </h1>
          <div className="text-right">
            <button
              onClick={fetchQQQData}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 mb-2"
            >
              Refresh Data
            </button>
            {lastUpdate && (
              <div className="text-sm text-gray-500">
                Last trading day:{" "}
                {new Date(lastUpdate).toLocaleDateString("en-US", {
                  weekday: "short",
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
              </div>
            )}
          </div>
        </div>

        {/* Alert Banner */}
        {alertMessage && (
          <div className="mb-6 p-4 bg-yellow-100 border-l-4 border-yellow-500 rounded">
            <div className="flex items-center">
              <AlertCircle className="w-6 h-6 text-yellow-600 mr-3" />
              <p className="text-lg font-semibold text-yellow-800">
                {alertMessage}
              </p>
            </div>
          </div>
        )}

        {/* Market Status Notice */}
        {lastUpdate &&
          new Date(lastUpdate).toDateString() !== new Date().toDateString() && (
            <div className="mb-6 p-4 bg-blue-50 border-l-4 border-blue-500 rounded">
              <div className="flex items-center">
                <AlertCircle className="w-5 h-5 text-blue-600 mr-3" />
                <p className="text-sm text-blue-800">
                  Markets are closed. Showing data from last trading day (
                  {new Date(lastUpdate).toLocaleDateString()}).
                  {new Date().getDay() === 0 || new Date().getDay() === 6
                    ? " Check back Monday after market close!"
                    : " Data will update after 4pm ET."}
                </p>
              </div>
            </div>
          )}

        {/* Current Status Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-gray-700">
                Current Signal
              </h2>
              <div className={getStatusColor()}>{getStatusIcon()}</div>
            </div>
            <p className={`text-3xl font-bold ${getStatusColor()}`}>{signal}</p>
            <p className="text-sm text-gray-500 mt-2">
              {signal === "TQQQ"
                ? "Buying TQQQ (3x leverage)"
                : "Holding Cash (0% market exposure)"}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-700 mb-4">
              QQQ Price
            </h2>
            <p className="text-3xl font-bold text-gray-800">
              ${currentPrice?.toFixed(2)}
            </p>
            <p className="text-sm text-gray-500 mt-2">Current market price</p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-700 mb-4">
              200-Day SMA
            </h2>
            <p className="text-3xl font-bold text-gray-800">
              ${sma200?.toFixed(2)}
            </p>
            <p
              className={`text-sm mt-2 ${parseFloat(percentFromSMA) >= 0 ? "text-green-600" : "text-red-600"}`}
            >
              {percentFromSMA}% from SMA
            </p>
          </div>
        </div>

        {/* Signal Zones */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <h2 className="text-2xl font-semibold text-gray-700 mb-4">
            Signal Zones
          </h2>
          <div className="space-y-4">
            <div className="flex items-center">
              <div className="w-4 h-4 bg-green-500 rounded mr-3"></div>
              <p className="text-gray-700">
                <strong>Buy Zone:</strong> QQQ ≥{" "}
                {(sma200 * (1 + BUFFER)).toFixed(2)}({BUFFER * 100}% above
                200-SMA) → Go 100% TQQQ
              </p>
            </div>
            <div className="flex items-center">
              <div className="w-4 h-4 bg-yellow-500 rounded mr-3"></div>
              <p className="text-gray-700">
                <strong>Hold Zone:</strong> Between{" "}
                {(sma200 * (1 - BUFFER)).toFixed(2)} and{" "}
                {(sma200 * (1 + BUFFER)).toFixed(2)} → Maintain current position
              </p>
            </div>
            <div className="flex items-center">
              <div className="w-4 h-4 bg-red-500 rounded mr-3"></div>
              <p className="text-gray-700">
                <strong>Sell Zone:</strong> QQQ ≤{" "}
                {(sma200 * (1 - BUFFER)).toFixed(2)}({BUFFER * 100}% below
                200-SMA) → Go 100% Cash
              </p>
            </div>
          </div>
        </div>

        {/* Performance Chart */}
        <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
          <h2 className="text-2xl font-semibold text-gray-700 mb-4">
            Performance Comparison (Recent History)
          </h2>
          <p className="text-sm text-gray-500 mb-6">
            Using real historical data for QQQ and TQQQ from Alpha Vantage.
            Monthly $2K contributions included.
          </p>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={performanceData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="date"
                tickFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <YAxis />
              <Tooltip
                formatter={(value) => `$${value.toLocaleString()}`}
                labelFormatter={(date) => new Date(date).toLocaleDateString()}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="lrs"
                stroke="#10b981"
                name="LRS Strategy"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="qqq"
                stroke="#3b82f6"
                name="Buy & Hold QQQ"
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="spy"
                stroke="#6366f1"
                name="Buy & Hold SPY"
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Next Steps */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-semibold text-gray-700 mb-4">
            Your Next Actions
          </h2>
          <div className="space-y-3">
            <p className="text-gray-700">
              ✅ <strong>Monday Purchase:</strong> Buying $5,000 of TQQQ
            </p>
            <p className="text-gray-700">
              📅 <strong>Monthly Contribution:</strong> $2,000 into {signal}
            </p>
            <p className="text-gray-700">
              🔔 <strong>Monitor:</strong> Check this dashboard daily for signal
              changes
            </p>
            <p className="text-gray-700 text-sm mt-4">
              💡 Tip: Set a reminder to check this page each evening after
              market close
            </p>
          </div>
        </div>

        {/* Disclaimer */}
        <div className="mt-8 p-4 bg-gray-100 rounded text-sm text-gray-600">
          <p className="mb-3">
            <strong>Disclaimer:</strong> This tool uses real market data from
            Alpha Vantage API for QQQ and TQQQ. Past performance does not
            guarantee future results. Leveraged ETFs like TQQQ involve
            significant risk, including volatility decay, and may not be
            suitable for all investors. TQQQ is designed for short-term trading
            and may not track 3x QQQ returns over longer periods. Always do your
            own research and consider consulting with a financial advisor before
            making investment decisions.
          </p>
          <p className="text-xs">
            <strong>API Setup:</strong> This app uses the 'demo' API key which
            has limited usage. For best results, get your own free API key at{" "}
            <a
              href="https://www.alphavantage.co/support/#api-key"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline"
            >
              alphavantage.co
            </a>{" "}
            (takes 30 seconds, no credit card required). Free tier includes 25
            requests per day - perfect for daily strategy monitoring!
          </p>
        </div>
      </div>
    </div>
  );
};

export default LRSTracker;
