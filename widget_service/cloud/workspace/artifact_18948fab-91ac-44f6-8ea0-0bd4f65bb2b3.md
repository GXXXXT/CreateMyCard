```cardspec
{
  "title": "设备充电",
  "description": "耳机手机充电状态",
  "suggestSize": "2x4",
  "imageDomainWhitelist": [
    "hag-ability-test.obs.cn-north-1.myhuaweicloud.com",
    "lfcontentcenterdev.hwcloudtest.cn",
    "hagres-drcn.dbankcdn.com"
  ],
  "dataBindings": [
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone"
    },
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery"
    }
  ]
}
```
```genui
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Row","children":["hero","aux"],"itemMargin":10,"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}}},{"id":"hero","component":"Column","children":["heroLabel","valueRow","heroSub"],"itemMargin":8,"styles":{"width":136,"height":126,"alignItems":"center","justifyContent":"center"}},{"id":"heroLabel","component":"Text","content":"手机剩余电量","styles":{"width":136,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"center","maxLines":1,"textOverflow":"clip"}},{"id":"valueRow","component":"Row","children":["valueNum","valueUnit"],"itemMargin":2,"styles":{"justifyContent":"center","alignItems":"bottom"}},{"id":"valueNum","component":"Text","content":"{{ ${/data/phoneBattery/batterySOC} }}","styles":{"fontSize":38,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1,"flexShrink":0,"textOverflow":"clip"}},{"id":"valueUnit","component":"Text","content":"%","styles":{"fontSize":16,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1,"flexShrink":0,"padding":{"bottom":6},"textOverflow":"clip"}},{"id":"heroSub","component":"Text","content":"{{ '手机' + ${/data/phoneBattery/chargingStatusDesc} }}","styles":{"width":136,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"center","maxLines":1,"textOverflow":"clip"}},{"id":"aux","component":"Column","children":["earSlot","batterySlot"],"itemMargin":8,"styles":{"width":130,"height":126}},{"id":"earSlot","component":"Column","children":["earTitle","earStatus"],"itemMargin":4,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}],"styles":{"width":130,"height":59,"padding":{"left":12,"right":12,"top":0,"bottom":0},"borderRadius":12,"backgroundColor":"#99FFFFFF","justifyContent":"center","alignItems":"start"}},{"id":"earTitle","component":"Text","content":"蓝牙设置","styles":{"width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1,"textOverflow":"clip"}},{"id":"earStatus","component":"Text","content":"{{ '耳机仓' + ${/data/earphone/chargingStatusDesc} }}","styles":{"width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1,"textOverflow":"clip"}},{"id":"batterySlot","component":"Column","children":["batTitle","batType"],"itemMargin":4,"onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}],"styles":{"width":130,"height":59,"padding":{"left":12,"right":12,"top":0,"bottom":0},"borderRadius":12,"backgroundColor":"#99FFFFFF","justifyContent":"center","alignItems":"start"}},{"id":"batTitle","component":"Text","content":"电池设置","styles":{"width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1,"textOverflow":"clip"}},{"id":"batType","component":"Text","content":"{{ ${/data/phoneBattery/pluggedTypeDesc} }}","styles":{"width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1,"textOverflow":"clip"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{"earphone":{"chargingStatusDesc":"未充电"},"phoneBattery":{"batterySOC":68,"chargingStatusDesc":"未充电","pluggedTypeDesc":"未连接充电器"}}}}}
```
```schema
{
  "schemaVersion": "widget-artifact-v2"
}
```
```taskspec
{
  "userQuery": "出门前想检查耳机仓和手机充电，帮我做个卡片，看耳机仓充电状态、手机剩余电量、手机充电状态和充电器类型，可以打开蓝牙设置，也可以打开电池设置。",
  "size": "2x4",
  "appVersion": "11.7.5.208",
  "eventCandidates": [
    {
      "id": "event.open.settings.bluetooth",
      "description": "打开系统设置的蓝牙设置页。",
      "call": "clickToDeeplink",
      "args": {
        "intentName": "Settings",
        "bundleName": "com.huawei.hmos.settings",
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "uri": "bluetooth_entry"
      }
    },
    {
      "id": "event.open.settings.battery",
      "description": "打开系统设置的电池页。",
      "call": "clickToDeeplink",
      "args": {
        "intentName": "Settings",
        "bundleName": "com.huawei.hmos.settings",
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "uri": "battery"
      }
    }
  ],
  "dataModelSchema": {
    "data": {
      "earphone": {
        "chargingStatusDesc": {
          "type": "string",
          "description": "耳机盒（或整体）当前的充电状态中文语义描述，'充电中' 或 '未充电'。",
          "sampleValue": "未充电"
        }
      },
      "phoneBattery": {
        "batterySOC": {
          "type": "integer",
          "description": "当前手机设备剩余电量的纯整数百分比，取值范围为 0 到 100，返回值不包含“%”。若直接用于文本展示，必须在数值后追加“%”；优先使用 batterySOCText。",
          "sampleValue": 68
        },
        "chargingStatusDesc": {
          "type": "string",
          "description": "当前设备电池的充电状态文本描述。",
          "sampleValue": "未充电"
        },
        "pluggedTypeDesc": {
          "type": "string",
          "description": "当前设备连接的充电器类型文本描述。",
          "sampleValue": "未连接充电器"
        }
      }
    }
  },
  "assetCandidates": [
    {
      "id": "asset.earphone_case_16644",
      "src": "resources/base/media/earphone_case_16644.svg",
      "description": "样式：耳机收纳盒实心图标，默认黑色，图形为无线耳机充电盒造型；适用：蓝牙耳机设备连接、音频设备管理。"
    },
    {
      "id": "asset.battery_leaf_fill",
      "src": "resources/base/media/battery_leaf_fill.svg",
      "description": "样式：默认黑色的单色实心横向电池图标，电池内部为叶片留白；适用：电池相关场景，包括电量、省电模式、节能电池、绿色用电状态，也可作为电池健康或电池温度信息的辅助图标，相关数据可结合 GetPhoneBatteryInfo 展示。图标本身不表示具体电量、健康等级或温度高低。"
    },
    {
      "id": "asset.bolt_fill",
      "src": "resources/base/media/bolt_fill.svg",
      "description": "样式：默认黑色的单色实心竖向闪电图标；适用：正在充电、快充、电能或闪电状态。"
    }
  ]
}
```
```effectivecapabilities
{
  "data": [
    "GetEarphoneInfo",
    "GetPhoneBatteryInfo"
  ],
  "event": [
    {
      "id": "event.open.settings.bluetooth",
      "description": "打开系统设置的蓝牙设置页。",
      "call": "clickToDeeplink",
      "args": {
        "intentName": "Settings",
        "bundleName": "com.huawei.hmos.settings",
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "uri": "bluetooth_entry"
      }
    },
    {
      "id": "event.open.settings.battery",
      "description": "打开系统设置的电池页。",
      "call": "clickToDeeplink",
      "args": {
        "intentName": "Settings",
        "bundleName": "com.huawei.hmos.settings",
        "abilityName": "com.huawei.hmos.settings.MainAbility",
        "uri": "battery"
      }
    }
  ],
  "asset": [
    "asset.earphone_case_16644",
    "asset.battery_leaf_fill",
    "asset.bolt_fill"
  ]
}
```
```removedcapabilities
[]
```
```generationplan
{
  "candidateDataBindings": [
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone",
      "candidateOutputFields": [
        "/chargingStatusDesc"
      ]
    },
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOC",
        "/chargingStatusDesc",
        "/pluggedTypeDesc"
      ]
    }
  ],
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.settings.bluetooth",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "intentName": "Settings",
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "bluetooth_entry"
        }
      }
    },
    {
      "capabilityId": "event.open.settings.battery",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "intentName": "Settings",
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "battery"
        }
      }
    }
  ],
  "candidateAssetIds": [
    "asset.earphone_case_16644",
    "asset.battery_leaf_fill",
    "asset.bolt_fill"
  ]
}
```
```meta
{
  "apiVersion": "v1",
  "taskSpecVersion": "task-spec-v1",
  "cardSpecVersion": "card-spec-v1",
  "dslProtocolVersion": "v0.9",
  "skillVersion": "skill-widget-v1",
  "protocolProfileId": "a2ui-form-rom6.0-v1",
  "capabilityRegistryVersion": "app-11.7.5.205_rom-6.0",
  "artifactSchemaVersion": "widget-artifact-v2",
  "generationMode": "create",
  "artifactId": "18948fab-91ac-44f6-8ea0-0bd4f65bb2b3",
  "createdAt": 1790912945046
}
```
```designcompactdsl
["root","Row",{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":20,"clip":true,"itemMargin":10,"justifyContent":"center","alignItems":"center","linearGradient":{"direction":"RightBottom","colors":[["#FFCBDDFE",0],["#FFF1F6FE",1]]}},["hero","aux"]]
["hero","Column",{"width":136,"height":126,"itemMargin":8,"alignItems":"center","justifyContent":"center"},["heroLabel","valueRow","heroSub"]]
["heroLabel","Text",{"content":"手机剩余电量","width":136,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"center","maxLines":1}]
["valueRow","Row",{"itemMargin":2,"justifyContent":"center","alignItems":"bottom"},["valueNum","valueUnit"]]
["valueNum","Text",{"content":{"path":"/data/phoneBattery/batterySOC"},"fontSize":38,"fontWeight":700,"fontColor":"#FF1F4799","maxLines":1,"flexShrink":0}]
["valueUnit","Text",{"content":"%","fontSize":16,"fontWeight":400,"fontColor":"#FF1F4799","maxLines":1,"flexShrink":0,"padding":{"bottom":6}}]
["heroSub","Text",{"content":"{{ '手机' + ${/data/phoneBattery/chargingStatusDesc} }}","width":136,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"center","maxLines":1}]
["aux","Column",{"width":130,"height":126,"itemMargin":8},["earSlot","batterySlot"]]
["earSlot","Column",{"width":130,"height":59,"padding":12,"borderRadius":12,"backgroundColor":"#99FFFFFF","itemMargin":4,"justifyContent":"center","alignItems":"start","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"bluetooth_entry"}}]},["earTitle","earStatus"]]
["earTitle","Text",{"content":"蓝牙设置","width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1}]
["earStatus","Text",{"content":"{{ '耳机仓' + ${/data/earphone/chargingStatusDesc} }}","width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1}]
["batterySlot","Column",{"width":130,"height":59,"padding":12,"borderRadius":12,"backgroundColor":"#99FFFFFF","itemMargin":4,"justifyContent":"center","alignItems":"start","onClick":[{"call":"clickToDeeplink","args":{"intentName":"Settings","bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"battery"}}]},["batTitle","batType"]]
["batTitle","Text",{"content":"电池设置","width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1}]
["batType","Text",{"content":{"path":"/data/phoneBattery/pluggedTypeDesc"},"width":106,"fontSize":12,"fontWeight":400,"fontColor":"#FF1F4799","textAlign":"start","maxLines":1}]
["/data/earphone/chargingStatusDesc","未充电"]
["/data/phoneBattery/batterySOC",68]
["/data/phoneBattery/chargingStatusDesc","未充电"]
["/data/phoneBattery/pluggedTypeDesc","未连接充电器"]
```
```request
{
  "content": {
    "bundleName": "com.omega_w_0823.hmservice",
    "userQuery": "出门前想检查耳机仓和手机充电，帮我做个卡片，看耳机仓充电状态、手机剩余电量、手机充电状态和充电器类型，可以打开蓝牙设置，也可以打开电池设置。",
    "candidateDataBindings": [
      {
        "capabilityId": "GetEarphoneInfo",
        "arguments": {},
        "writeResultTo": "/data/earphone",
        "candidateOutputFields": [
          "/chargingStatusDesc"
        ]
      },
      {
        "capabilityId": "GetPhoneBatteryInfo",
        "arguments": {},
        "writeResultTo": "/data/phoneBattery",
        "candidateOutputFields": [
          "/batterySOC",
          "/chargingStatusDesc",
          "/pluggedTypeDesc"
        ]
      }
    ],
    "title": "设备充电",
    "size": "2x4",
    "candidateEventCandidates": [
      {
        "capabilityId": "event.open.settings.bluetooth",
        "action": {
          "call": "clickToDeeplink",
          "args": {
            "intentName": "Settings",
            "bundleName": "com.huawei.hmos.settings",
            "abilityName": "com.huawei.hmos.settings.MainAbility",
            "uri": "bluetooth_entry"
          }
        }
      },
      {
        "capabilityId": "event.open.settings.battery",
        "action": {
          "call": "clickToDeeplink",
          "args": {
            "intentName": "Settings",
            "bundleName": "com.huawei.hmos.settings",
            "abilityName": "com.huawei.hmos.settings.MainAbility",
            "uri": "battery"
          }
        }
      }
    ],
    "description": "耳机手机充电状态",
    "candidateAssetIds": [
      "asset.earphone_case_16644",
      "asset.battery_leaf_fill",
      "asset.bolt_fill"
    ]
  },
  "deviceInfo": {
    "countryCode": "CN",
    "deviceFormation": "HDSpeaker",
    "deviceType": 0,
    "locale": "zh-CN",
    "phoneType": "SGT-AL10",
    "prdVer": "11.7.5.208",
    "sysVer": "EmotionUI_9.0.0",
    "time": "20260828000000000"
  },
  "pagination": {
    "limit": 5,
    "start": ""
  },
  "session": {
    "interactionId": "060",
    "isNew": true,
    "sessionId": "taskspec-829.2"
  },
  "userAuth": {
    "user": {}
  },
  "utterance": {
    "original": "出门前想检查耳机仓和手机充电，帮我做个卡片，看耳机仓充电状态、手机剩余电量、手机充电状态和充电器类型，可以打开蓝牙设置，也可以打开电池设置。",
    "type": "text"
  },
  "version": "1.0",
  "bundleName": "com.omega_w_0823.hmservice",
  "userQuery": "出门前想检查耳机仓和手机充电，帮我做个卡片，看耳机仓充电状态、手机剩余电量、手机充电状态和充电器类型，可以打开蓝牙设置，也可以打开电池设置。",
  "candidateDataBindings": [
    {
      "capabilityId": "GetEarphoneInfo",
      "arguments": {},
      "writeResultTo": "/data/earphone",
      "candidateOutputFields": [
        "/chargingStatusDesc"
      ]
    },
    {
      "capabilityId": "GetPhoneBatteryInfo",
      "arguments": {},
      "writeResultTo": "/data/phoneBattery",
      "candidateOutputFields": [
        "/batterySOC",
        "/chargingStatusDesc",
        "/pluggedTypeDesc"
      ]
    }
  ],
  "title": "设备充电",
  "size": "2x4",
  "candidateEventCandidates": [
    {
      "capabilityId": "event.open.settings.bluetooth",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "intentName": "Settings",
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "bluetooth_entry"
        }
      }
    },
    {
      "capabilityId": "event.open.settings.battery",
      "action": {
        "call": "clickToDeeplink",
        "args": {
          "intentName": "Settings",
          "bundleName": "com.huawei.hmos.settings",
          "abilityName": "com.huawei.hmos.settings.MainAbility",
          "uri": "battery"
        }
      }
    }
  ],
  "description": "耳机手机充电状态",
  "candidateAssetIds": [
    "asset.earphone_case_16644",
    "asset.battery_leaf_fill",
    "asset.bolt_fill"
  ]
}
```
