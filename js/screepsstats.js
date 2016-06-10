
var ScreepsStats = function () {
  if(!Memory.___screeps_stats) {
    Memory.___screeps_stats = {}
  }

  if(!!Game.structures.length > 0) {
    this.username = Game.structures[0].owner.username
  } else if (Game.creeps.length > 0) {
    this.username = Game.creeps[0].owner.username
  } else {
    this.username = false
  }
  this.clean()
}

ScreepsStats.prototype.clean = function () {
  var recorded = Object.keys(Memory.___screeps_stats)
  if(recorded.length > 20) {
    recorded.sort()
    var limit = recorded.length - 20
    for(var i = 0; i < limit; i++) {
      this.removeTick(recorded[i])
    }
  }
}

ScreepsStats.prototype.addStat = function (key, value) {

  // Key is in format 'parent.child.grandchild.greatgrantchild.etc'

  var key_split = key.split('.')

  if(key_split.length == 1) {
    Memory.___screeps_stats[Game.time][key_split[0]] = value
    return
  }

  start = Memory.___screeps_stats[Game.time][key_split[0]]

  var tmp = {}
  for (var i=0,n=key_split.length; i<n; i++){
    if(i == (n-1)) {
      tmp[arr[i]]=value;
    } else {
      tmp[arr[i]]={};
      tmp = tmp[arr[i]];
    }
  }

  _.merge(start = Memory.___screeps_stats[Game.time], tmp)
}


ScreepsStats.prototype.runBuiltinStats = function () {

  stats = {}
  stats.time = new Date().toString()
  stats.tick = Game.time

  stats['cpu'] = {
    'limit': Game.cpu.limit,
    'tickLimit': Game.cpu.tickLimit,
    'bucket': Game.cpu.bucket
  }

  stats['gcl'] = {
    'level': Game.gcl.level,
    'progress': Game.gcl.progress,
    'progressTotal': Game.gcl.progressTotal
  }

  if(!stats['rooms']) {
    stats['rooms'] = {}
  }


  for(var roomName in Game.rooms) {
    var room = Game.rooms[roomName]

    if(!stats[roomName]) {
      stats['rooms'][roomName] = {}
    }

    if(!!room.controller) {
      var controller = room.controller

      // Is hostile room? Continue
      if(!controller.my) {
        if(!!controller.owner) { // Owner is set but is not this user.
          if(controller.owner.username != this.username) {
            continue
          }
        }
      }

      // Collect stats
      stats['rooms'][roomName]['level'] = controller.level
      stats['rooms'][roomName]['progress'] = controller.progress

      if(!!controller.upgradeBlocked) {
        stats['rooms'][roomName]['upgradeBlocked'] = controller.upgradeBlocked
      }

      if(!!controller.reservation) {
        stats['rooms'][roomName]['reservation'] = controller.reservation.ticksToEnd
      }

      if(!!controller.ticksToDowngrade) {
        stats['rooms'][roomName]['ticksToDowngrade'] = controller.ticksToDowngrade
      }

      if(controller.level > 0) {

        stats['rooms'][roomName]['energyAvailable'] = room.energyAvailable
        stats['rooms'][roomName]['energyAvailable'] = room.energyCapacityAvailable

        if(room.storage) {
          stats['rooms'][roomName]['storage'] = {}
          stats['rooms'][roomName]['storage'].store = _.sum(room.storage.store)
          stats['rooms'][roomName]['storage']['resources'] = {}
          for(var resourceType in room.storage.store) {
            stats['rooms'][roomName]['storage']['resources'][resourceType] = room.storage.store[resourceType]
          }
        }

        if(room.terminal) {
          stats['rooms'][roomName]['terminal'] = {}
          stats['rooms'][roomName]['terminal'].store = _.sum(room.terminal.store)
          stats['rooms'][roomName]['terminal']['resources'] = {}
          for(var resourceType in room.terminal.store) {
            stats['rooms'][roomName]['terminal']['resources'][resourceType] = room.terminal.store[resourceType]
          }
        }
      }
    }

    this.roomExpensive(stats,room)
  }

  for(var i in Game.spawns) {
    var spawn = Game.spawns[i]
    var roomName = spawn.room.name

    if(!stats['rooms'][roomName]['spawns']) {
      stats['rooms'][roomName]['spawns'] = {}
    }

    stats['rooms'][roomName]['spawns'][spawn.name] = {}
    if(!!spawn.spawning) {
      stats['rooms'][roomName]['spawns'][spawn.name].busy = true
      stats['rooms'][roomName]['spawns'][spawn.name].remainingTime = spawn.spawning.remainingTime
    } else {
      stats['rooms'][roomName]['spawns'][spawn.name].busy = false
      stats['rooms'][roomName]['spawns'][spawn.name].remainingTime = 0
    }
  }

  Memory.___screeps_stats[Game.time] = stats
}




ScreepsStats.prototype.roomExpensive = function (stats, room) {

  var roomName = room.name


  // Source Mining
  var sources = room.find(FIND_SOURCES)
  stats['rooms'][roomName]['sources'] = {}
  for(var source_index in sources) {
    var source = sources[source_index]
    stats['rooms'][roomName]['sources'][source.id] = {}
    stats['rooms'][roomName]['sources'][source.id].energy = source.energy
    stats['rooms'][roomName]['sources'][source.id].energyCapacity = source.energyCapacity
    stats['rooms'][roomName]['sources'][source.id].ticksToRegeneration = source.ticksToRegeneration
  }

  // Mineral Mining
  var minerals = room.find(FIND_MINERALS)
  stats['rooms'][roomName]['minerals'] = {}
  for(var minerals_index in minerals) {
    var mineral = minerals[minerals_index]
    stats['rooms'][roomName]['minerals'][mineral.id] = {}
    stats['rooms'][roomName]['minerals'][mineral.id].mineralType = mineral.mineralType
    stats['rooms'][roomName]['minerals'][mineral.id].mineralAmount = mineral.mineralAmount
    stats['rooms'][roomName]['minerals'][mineral.id].ticksToRegeneration = mineral.ticksToRegeneration
  }


  // Hostiles in Room
  var hostiles = room.find(FIND_HOSTILE_CREEPS)
  stats['rooms'][roomName]['hostiles'] = {}
  for(var hostile_index in hostiles){
    var hostile = hostiles[hostile_index]
    if(!stats[roomName]['hostiles'][hostile.owner.username]) {
      stats['rooms'][roomName]['hostiles'][hostile.owner.username] = 1
    } else {
      stats['rooms'][roomName]['hostiles'][hostile.owner.username]++
    }
  }

  // My Creeps
  stats['rooms'][roomName]['creeps'] = room.find(FIND_MY_CREEPS).length
}


ScreepsStats.prototype.removeTick = function (tick) {
  if(!!Memory.___screeps_stats[tick]) {
    delete Memory.___screeps_stats[tick]
  }
}

ScreepsStats.prototype.getStats = function (json) {
  if(json) {
    return JSON.stringify(Memory.___screeps_stats)
  } else {
    return Memory.__screeps_stats
  }
}

ScreepsStats.prototype.getStatsForTick = function (tick) {
  if(!Memory.__screeps_stats[tick]) {
    return false
  } else {
    return Memory.__screeps_stats[tick]
  }
}



module.exports = ScreepsStats