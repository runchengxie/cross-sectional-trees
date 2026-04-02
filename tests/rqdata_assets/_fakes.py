import pandas as pd


class _FakeRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        rows: list[dict] = []
        index: list[tuple[str, str]] = []
        for order_book_id in order_book_ids:
            if order_book_id == "00005.XHKG":
                rows.extend(
                    [
                        {
                            "info_date": pd.Timestamp("2025-03-20"),
                            "fiscal_year": pd.Timestamp("2024-12-31"),
                            "standard": "IFRS",
                            "if_adjusted": 0,
                            "rice_create_tm": pd.Timestamp("2025-03-20 09:00:00"),
                            "revenue": 100.0,
                            "net_profit": 10.0,
                        },
                        {
                            "info_date": pd.Timestamp("2025-08-20"),
                            "fiscal_year": pd.Timestamp("2025-12-31"),
                            "standard": "IFRS",
                            "if_adjusted": 0,
                            "rice_create_tm": pd.Timestamp("2025-08-20 09:00:00"),
                            "revenue": 120.0,
                            "net_profit": 12.0,
                        },
                    ]
                )
                index.extend([(order_book_id, "2024q4"), (order_book_id, "2025q1")])
            elif order_book_id == "00011.XHKG":
                rows.append(
                    {
                        "info_date": pd.Timestamp("2025-08-25"),
                        "fiscal_year": pd.Timestamp("2025-12-31"),
                        "standard": "IFRS",
                        "if_adjusted": 1,
                        "rice_create_tm": pd.Timestamp("2025-08-25 09:00:00"),
                        "revenue": 220.0,
                        "net_profit": 22.0,
                    }
                )
                index.append((order_book_id, "2025q1"))
        if not rows:
            empty_columns = list(fields) if fields else []
            return pd.DataFrame(
                columns=empty_columns,
                index=pd.MultiIndex.from_arrays([[], []], names=["order_book_id", "info_date"]),
            )
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(index, names=["order_book_id", "quarter"]),
        )

class _WhitespaceFieldRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        return pd.DataFrame(
            [
                {
                    "info_date": pd.Timestamp("2025-03-20"),
                    "fiscal_year": pd.Timestamp("2024-12-31"),
                    "standard": "IFRS",
                    "if_adjusted": 0,
                    "rice_create_tm": pd.Timestamp("2025-03-20 09:00:00"),
                    "revenue": 100.0,
                    "goodwill_and_intangible_assets ": 55.0,
                }
            ],
            index=pd.MultiIndex.from_tuples(
                [("00005.XHKG", "2024q4")],
                names=["order_book_id", "quarter"],
            ),
        )

class _FakeRQHKApi:
    def __init__(self):
        self.calls: list[dict] = []

    def get_detailed_financial_items(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        rows = [
            {
                "info_date": pd.Timestamp("2025-03-20"),
                "fiscal_year": pd.Timestamp("2024-12-31"),
                "field": "revenue",
                "relationship": 1.0,
                "amount": 70.0,
                "currency": "港元",
                "subject": "保费收入",
                "standard": "IFRS",
                "if_adjusted": 0,
            },
            {
                "info_date": pd.Timestamp("2025-03-20"),
                "fiscal_year": pd.Timestamp("2024-12-31"),
                "field": "revenue",
                "relationship": 1.0,
                "amount": 30.0,
                "currency": "港元",
                "subject": "手续费收入",
                "standard": "IFRS",
                "if_adjusted": 0,
            },
        ]
        return pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(
                [("00005.XHKG", "2024q4"), ("00005.XHKG", "2024q4")],
                names=["order_book_id", "quarter"],
            ),
        )

class _FakeRQDetailsClient:
    def __init__(self):
        self.hk = _FakeRQHKApi()

class _FakeRQInstrumentsClient:
    def __init__(self):
        self.calls: list[dict] = []

    def all_instruments(self, instrument_type, market="hk"):
        self.calls.append({"instrument_type": instrument_type, "market": market})
        return pd.DataFrame(
            [
                {
                    "order_book_id": "00005.XHKG",
                    "symbol": "HSBC HOLDINGS",
                    "listed_date": pd.Timestamp("2000-01-03"),
                    "de_listed_date": pd.NaT,
                    "round_lot": 400,
                    "board_type": "Main Board",
                    "status": "Active",
                },
                {
                    "order_book_id": "00700.XHKG",
                    "symbol": "TENCENT",
                    "listed_date": pd.Timestamp("2004-06-16"),
                    "de_listed_date": pd.NaT,
                    "round_lot": 100,
                    "board_type": "Main Board",
                    "status": "Active",
                },
            ]
        )

class _FakeRQDailyInstrument:
    def __init__(self, listed_date: str):
        self.listed_date = listed_date

class _FakeRQDailyMirrorClient:
    def __init__(self):
        self.price_calls: list[dict] = []
        self._listed_dates = {
            "00005.XHKG": "2000-01-03",
            "00011.XHKG": "2004-06-16",
            "00012.XHKG": "2026-01-15",
        }
        self._payloads = {
            "00005.XHKG": pd.DataFrame(
                {
                    "open": [10.0, 11.0],
                    "high": [11.0, 12.0],
                    "low": [9.5, 10.5],
                    "close": [10.5, 11.5],
                    "volume": [1000.0, 1200.0],
                    "total_turnover": [10000.0, 12000.0],
                },
                index=pd.to_datetime(["2025-01-02", "2025-01-03"]),
            ),
            "00011.XHKG": pd.DataFrame(
                {
                    "open": [20.0],
                    "high": [21.0],
                    "low": [19.5],
                    "close": [20.5],
                    "volume": [2000.0],
                    "total_turnover": [30000.0],
                },
                index=pd.to_datetime(["2025-01-03"]),
            ),
        }

    def instruments(self, order_book_id, market=None):
        return _FakeRQDailyInstrument(self._listed_dates.get(order_book_id, "2000-01-03"))

    def get_price(self, order_book_id, start_date, end_date, frequency, **kwargs):
        self.price_calls.append(
            {
                "order_book_id": order_book_id,
                "start_date": start_date,
                "end_date": end_date,
                "frequency": frequency,
                "kwargs": dict(kwargs),
            }
        )
        if isinstance(order_book_id, list):
            frames: list[pd.DataFrame] = []
            for item in order_book_id:
                payload = self._payloads.get(item)
                if payload is None or payload.empty:
                    continue
                current = payload.copy()
                current.index = pd.MultiIndex.from_arrays(
                    [[item] * len(current.index), current.index],
                    names=["order_book_id", "trade_date"],
                )
                frames.append(current)
            if not frames:
                return pd.DataFrame()
            return pd.concat(frames)
        payload = self._payloads.get(order_book_id)
        if payload is not None:
            return payload.copy()
        return pd.DataFrame()

class _FakeRQValuationClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_factor(self, order_book_ids, factors, start_date=None, end_date=None, **kwargs):
        request_ids = [str(item) for item in (order_book_ids if isinstance(order_book_ids, list) else [order_book_ids])]
        self.calls.append(
            {
                "order_book_ids": request_ids,
                "factors": list(factors) if isinstance(factors, (list, tuple)) else [str(factors)],
                "start_date": start_date,
                "end_date": end_date,
                "kwargs": dict(kwargs),
            }
        )
        frames: list[pd.DataFrame] = []
        if "00005.XHKG" in request_ids:
            frames.append(
                pd.DataFrame(
                    {
                        "hk_total_market_val": [1000.0, 1010.0],
                        "pe_ratio_ttm": [8.0, 8.1],
                        "pb_ratio_ttm": [1.1, 1.2],
                    },
                    index=pd.MultiIndex.from_tuples(
                        [
                            ("00005.XHKG", pd.Timestamp("2025-01-02")),
                            ("00005.XHKG", pd.Timestamp("2025-01-03")),
                        ],
                        names=["order_book_id", "date"],
                    ),
                )
            )
        if "00011.XHKG" in request_ids:
            frames.append(
                pd.DataFrame(
                    {
                        "hk_total_market_val": [2000.0],
                        "pe_ratio_ttm": [10.5],
                        "pb_ratio_ttm": [1.4],
                    },
                    index=pd.MultiIndex.from_tuples(
                        [("00011.XHKG", pd.Timestamp("2025-01-03"))],
                        names=["order_book_id", "date"],
                    ),
                )
            )
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames).sort_index()

class _FakeRQValuationTradeDateColumnClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_factor(self, order_book_ids, factors, start_date=None, end_date=None, **kwargs):
        request_ids = [str(item) for item in (order_book_ids if isinstance(order_book_ids, list) else [order_book_ids])]
        self.calls.append(
            {
                "order_book_ids": request_ids,
                "factors": list(factors) if isinstance(factors, (list, tuple)) else [str(factors)],
                "start_date": start_date,
                "end_date": end_date,
                "kwargs": dict(kwargs),
            }
        )
        return pd.DataFrame(
            {
                "trade_date": [pd.Timestamp("2026-03-27")],
                "hk_total_market_val": [1000.0],
                "pe_ratio_ttm": [8.0],
                "pb_ratio_ttm": [1.1],
            },
            index=pd.MultiIndex.from_tuples(
                [("00005.XHKG", pd.Timestamp("2026-03-27"))],
                names=["order_book_id", "date"],
            ),
        )

class _FakeRQExchangeRateClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_exchange_rate(self, start_date=None, end_date=None, fields=None):
        self.calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "fields": list(fields) if fields else None,
            }
        )
        frame = pd.DataFrame(
            [
                {
                    "currency_pair": "HKDCNY",
                    "middle_referrence_rate": 0.9384,
                    "bid_referrence_rate": 0.9165,
                    "ask_referrence_rate": 0.9731,
                    "bid_settlement_rate_sh": 0.94448,
                    "ask_settlement_rate_sh": 0.94481,
                    "bid_settlement_rate_sz": 0.94479,
                    "ask_settlement_rate_sz": 0.94481,
                },
                {
                    "currency_pair": "HKDUSD",
                    "middle_referrence_rate": 0.1284,
                    "bid_referrence_rate": pd.NA,
                    "ask_referrence_rate": pd.NA,
                    "bid_settlement_rate_sh": pd.NA,
                    "ask_settlement_rate_sh": pd.NA,
                    "bid_settlement_rate_sz": pd.NA,
                    "ask_settlement_rate_sz": pd.NA,
                },
                {
                    "currency_pair": "HKDCNY",
                    "middle_referrence_rate": 0.9391,
                    "bid_referrence_rate": 0.9174,
                    "ask_referrence_rate": 0.9742,
                    "bid_settlement_rate_sh": 0.94545,
                    "ask_settlement_rate_sh": 0.94582,
                    "bid_settlement_rate_sz": 0.94578,
                    "ask_settlement_rate_sz": 0.94582,
                },
            ],
            index=pd.Index(
                pd.to_datetime(["2025-02-10", "2025-02-10", "2025-02-11"]),
                name="date",
            ),
        )
        if fields:
            return frame.loc[:, list(fields)].copy()
        return frame

class _FakeRQExFactorClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_ex_factor(self, order_book_ids, start_date=None, end_date=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "market": market,
            }
        )
        rows = [
            {
                "order_book_id": "00005.XHKG",
                "ex_date": pd.Timestamp("2025-03-19"),
                "announcement_date": pd.Timestamp("2025-03-10"),
                "ex_factor": 0.98,
                "ex_cum_factor": 1.25,
                "ex_end_date": pd.Timestamp("2025-03-21"),
            },
            {
                "order_book_id": "00005.XHKG",
                "ex_date": pd.Timestamp("2025-09-19"),
                "announcement_date": pd.Timestamp("2025-09-10"),
                "ex_factor": 0.97,
                "ex_cum_factor": 1.21,
                "ex_end_date": pd.Timestamp("2025-09-23"),
            },
        ]
        frame = pd.DataFrame(rows).set_index("ex_date")
        frame.index.name = "ex_date"
        return frame

class _FakeRQDividendClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_dividend(self, order_book_ids, start_date=None, end_date=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "market": market,
            }
        )
        return pd.DataFrame(
            {
                "book_closure_date": [pd.Timestamp("2025-03-24"), pd.Timestamp("2025-09-24")],
                "ex_dividend_date": [pd.Timestamp("2025-03-19"), pd.Timestamp("2025-09-19")],
                "payable_date": [pd.Timestamp("2025-04-10"), pd.Timestamp("2025-10-10")],
                "dividend_cash_before_tax": [0.5, 0.6],
                "round_lot": [400, 400],
            },
            index=pd.MultiIndex.from_tuples(
                [
                    ("00005.XHKG", pd.Timestamp("2025-03-10")),
                    ("00005.XHKG", pd.Timestamp("2025-09-10")),
                ],
                names=["order_book_id", "declaration_announcement_date"],
            ),
        )

class _FakeRQSharesClient:
    def __init__(self):
        self.calls: list[dict] = []

    def get_shares(self, order_book_ids, start_date=None, end_date=None, fields=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "fields": list(fields or []),
                "market": market,
            }
        )
        return pd.DataFrame(
            {
                "total": [5_000_000_000, 5_100_000_000],
                "total_hk": [4_900_000_000, 5_000_000_000],
                "total_hk1": [4_800_000_000, 4_900_000_000],
            },
            index=pd.MultiIndex.from_tuples(
                [
                    ("00005.XHKG", pd.Timestamp("2025-01-31")),
                    ("00005.XHKG", pd.Timestamp("2025-06-30")),
                ],
                names=["order_book_id", "date"],
            ),
        )

class _FakeRQIndustryClient:
    def __init__(self):
        self.instrument_calls: list[dict] = []
        self.mapping_calls: list[dict] = []
        self.change_calls: list[dict] = []

    def get_instrument_industry(self, order_book_ids, source="citics_2019", level=1, date=None, market="hk"):
        self.instrument_calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "source": source,
                "level": level,
                "date": date,
                "market": market,
            }
        )
        rows: list[dict] = []
        index: list[str] = []
        for order_book_id in order_book_ids:
            if order_book_id == "00005.XHKG":
                rows.append(
                    {
                        "first_industry_code": "40",
                        "first_industry_name": "银行",
                        "second_industry_code": "4020",
                        "second_industry_name": "全国性股份制银行Ⅱ",
                        "third_industry_code": "402010",
                        "third_industry_name": "全国性股份制银行Ⅲ",
                    }
                )
                index.append(order_book_id)
            elif order_book_id == "00700.XHKG":
                rows.append(
                    {
                        "first_industry_code": "63",
                        "first_industry_name": "传媒",
                        "second_industry_code": "6340",
                        "second_industry_name": "互联网媒体",
                        "third_industry_code": "634020",
                        "third_industry_name": "社交与互动媒体",
                    }
                )
                index.append(order_book_id)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows, index=pd.Index(index, name="order_book_id"))

    def get_industry_mapping(self, source="citics_2019", date=None, market="hk"):
        self.mapping_calls.append({"source": source, "date": date, "market": market})
        return pd.DataFrame(
            [
                {
                    "first_industry_code": "40",
                    "first_industry_name": "银行",
                    "second_industry_code": "4020",
                    "second_industry_name": "全国性股份制银行Ⅱ",
                    "third_industry_code": "402010",
                    "third_industry_name": "全国性股份制银行Ⅲ",
                },
                {
                    "first_industry_code": "63",
                    "first_industry_name": "传媒",
                    "second_industry_code": "6340",
                    "second_industry_name": "互联网媒体",
                    "third_industry_code": "634020",
                    "third_industry_name": "社交与互动媒体",
                },
            ]
        )

    def get_industry_change(self, industry, source="citics_2019", level=None, market="hk"):
        self.change_calls.append(
            {
                "industry": industry,
                "source": source,
                "level": level,
                "market": market,
            }
        )
        if industry == "40":
            return pd.DataFrame(
                {
                    "start_date": [pd.Timestamp("2000-01-03")],
                    "cancel_date": [pd.Timestamp("2200-12-31")],
                },
                index=pd.Index(["00005.XHKG"], name="order_book_id"),
            )
        if industry == "63":
            return pd.DataFrame(
                {
                    "start_date": [pd.Timestamp("2004-06-16")],
                    "cancel_date": [pd.Timestamp("2200-12-31")],
                },
                index=pd.Index(["00700.XHKG"], name="order_book_id"),
            )
        return pd.DataFrame()

class _FakeRQSouthboundHKApi:
    def __init__(self):
        self.calls: list[dict] = []
        self._payloads = {
            ("sh", "20250102"): ["00005.XHKG"],
            ("sz", "20250102"): ["00011.XHKG"],
            ("sh", "20250131"): [],
            ("sz", "20250131"): ["00011.XHKG"],
        }

    def get_southbound_eligible_secs(self, trading_type=None, date=None):
        self.calls.append({"trading_type": trading_type, "date": date})
        return list(self._payloads.get((trading_type, date), []))

class _FakeRQSouthboundClient:
    def __init__(self):
        self.hk = _FakeRQSouthboundHKApi()

class _FakeRQAnnouncementHKApi:
    def __init__(self):
        self.calls: list[dict] = []

    def get_announcement(self, *, order_book_ids, start_date=None, end_date=None, fields=None, market="hk"):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "start_date": start_date,
                "end_date": end_date,
                "fields": None if fields is None else list(fields),
                "market": market,
            }
        )
        rows: list[dict] = []
        index: list[tuple[str, pd.Timestamp]] = []
        for order_book_id in order_book_ids:
            if order_book_id == "00005.XHKG":
                rows.append(
                    {
                        "media": "HKEXnews",
                        "title": "FY2024 results",
                        "language": "EN",
                        "file_type": "pdf",
                        "announcement_link": "https://example.com/00005",
                        "first_category": "Results",
                        "second_category": "Annual",
                        "third_category": "Final",
                        "rice_create_tm": pd.Timestamp("2025-03-20 09:00:00"),
                    }
                )
                index.append((order_book_id, pd.Timestamp("2025-03-20")))
            elif order_book_id == "00011.XHKG":
                rows.extend(
                    [
                        {
                            "media": "HKEXnews",
                            "title": "Special dividend",
                            "language": "EN",
                            "file_type": "pdf",
                            "announcement_link": "https://example.com/00011-1",
                            "first_category": "Dividend",
                            "second_category": "Special",
                            "third_category": "Cash",
                            "rice_create_tm": pd.Timestamp("2025-03-21 09:15:00"),
                        },
                        {
                            "media": "HKEXnews",
                            "title": "2024 annual report",
                            "language": "EN",
                            "file_type": "pdf",
                            "announcement_link": "https://example.com/00011-2",
                            "first_category": "Report",
                            "second_category": "Annual",
                            "third_category": "Final",
                            "rice_create_tm": pd.Timestamp("2025-03-24 07:30:00"),
                        },
                    ]
                )
                index.extend(
                    [
                        (order_book_id, pd.Timestamp("2025-03-21")),
                        (order_book_id, pd.Timestamp("2025-03-24")),
                    ]
                )
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(index, names=["order_book_id", "info_date"]),
        )
        if fields:
            available = [field for field in fields if field in frame.columns]
            frame = frame.loc[:, available]
        return frame

class _FakeRQAnnouncementClient:
    def __init__(self):
        self.hk = _FakeRQAnnouncementHKApi()

class _FlakyRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._delegate = _FakeRQPitClient()
        self._failed_once = False

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        if not self._failed_once:
            self._failed_once = True
            raise ConnectionError("temporary network jitter")
        return self._delegate.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=fields,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            date=date,
            statements=statements,
            market=market,
        )

class _QuotaRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._delegate = _FakeRQPitClient()

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        payload = {
            "order_book_ids": list(order_book_ids),
            "fields": list(fields),
            "start_quarter": start_quarter,
            "end_quarter": end_quarter,
            "date": date,
            "statements": statements,
            "market": market,
        }
        self.calls.append(payload)
        if len(self.calls) >= 2:
            raise RuntimeError("daily quota exceeded: bytes_limit reached")
        return self._delegate.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=fields,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            date=date,
            statements=statements,
            market=market,
        )

class _QuotaRQDailyMirrorClient(_FakeRQDailyMirrorClient):
    def get_price(self, order_book_id, start_date, end_date, frequency, **kwargs):
        if len(self.price_calls) >= 1:
            self.price_calls.append(
                {
                    "order_book_id": order_book_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "frequency": frequency,
                    "kwargs": dict(kwargs),
                }
            )
            raise RuntimeError("daily quota exceeded: bytes_limit reached")
        return super().get_price(order_book_id, start_date, end_date, frequency, **kwargs)

class _SplitBatchRQDailyMirrorClient(_FakeRQDailyMirrorClient):
    def get_price(self, order_book_id, start_date, end_date, frequency, **kwargs):
        if isinstance(order_book_id, list) and len(order_book_id) > 1:
            self.price_calls.append(
                {
                    "order_book_id": order_book_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "frequency": frequency,
                    "kwargs": dict(kwargs),
                }
            )
            raise RuntimeError("temporary batch failure")
        return super().get_price(order_book_id, start_date, end_date, frequency, **kwargs)

class _FieldFallbackRQPitClient:
    def __init__(self):
        self.calls: list[dict] = []
        self._delegate = _FakeRQPitClient()

    def get_pit_financials_ex(
        self,
        *,
        order_book_ids,
        fields,
        start_quarter,
        end_quarter,
        date=None,
        statements="latest",
        market="hk",
    ):
        self.calls.append(
            {
                "order_book_ids": list(order_book_ids),
                "fields": list(fields),
                "start_quarter": start_quarter,
                "end_quarter": end_quarter,
                "date": date,
                "statements": statements,
                "market": market,
            }
        )
        if "goodwill_and_intangible_assets" in fields:
            raise RuntimeError(
                "fields: got invalided value goodwill_and_intangible_assets, choose any in ['revenue', 'net_profit']"
            )
        return self._delegate.get_pit_financials_ex(
            order_book_ids=order_book_ids,
            fields=fields,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            date=date,
            statements=statements,
            market=market,
        )
