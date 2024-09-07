from pprint import pformat
from string import ascii_letters, punctuation
from requests import get, post

class Video:
    def __init__(self, id, key, size="??? MB"):
        self.id = id
        self.key = key
        self.size = size

    def __str__(self) -> str:
        return "Video {{ id: {id}, key: {key}, size: {size} }}".format(id=self.id,
                                                                   key=self.key,
                                                                   size=self.size,
                                                                   )
    def __repr__(self) -> str:
        return self.__str__()

class YTDownloader:
    __host = "https://www.y2mate.com"
    __analyze_endpoint = "/mates/analyzeV2/ajax"
    __convert_endpoint =  "/mates/convertV2/index"
    __default_headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                         "Referer": "https://www.y2mate.com/",
                         }

    def __init__(self):
        self.__target = ''
        self.__data = {}
  
    def __check_data(self) -> bool:
        if self.__data == {}:
            return False
        return True
    
    def __check_target(self) -> bool:
        if self.__target == '':
            return False
        return True

    def __reset_data(self):
        self.__data = {}

    def __verify_url(self, url):
        if url.startswith("https://"):
            return True
        return False

    def set_target(self, url:str):
        if not self.__verify_url(url):
            raise ValueError("error: url inválida")
        self.__target = url
    
    def reset_target(self):
        self.__target = ''
        self.__reset_data()

    def get_info(self):
        if not self.__check_target():
            raise Exception("error: no hay url objetivo")        
        info = self.__analyze(self.__target)
        return self.__save_info(info)

    def download(self, calidad:str):
        try:
            vid = self.__data["qualities"][calidad]
            self.__download(vid)
        except KeyError:
            print("error: calidad no disponible -> {}".format(calidad))
            exit(1)
        self.reset_target()

    def __download(self, video):
        link = self.__get_download_link(video)
        response = get(link,
                       headers=self.__default_headers,
                       stream=True)
        CHUNK_SIZE = 1024
        iterator = response.iter_content(CHUNK_SIZE)
        target_size = int(response.headers["Content-Length"].strip())
        downloaded = 0
        video_title = self.get_video_name()
        LENGTH_BAR = 50

        def update_bar(done, target, length_bar):
            p = done / target
            buffer = '['
            asterisc = round(length_bar*p)
            buffer += '*'*asterisc
            minus = length_bar - asterisc
            buffer += '-'*minus
            buffer += '] {} % ({} MB / {} MB)'.format(round(p*100),
                                                      round(done / 1000000, 3),
                                                      round(target / 1000000, 3),
                                                      )
            return buffer

        with open(video_title+".mp4", "wb") as file:
            print("Downloading video: {}.mp4".format(video_title))
            for chunk in iterator:
                file.write(chunk)
                downloaded += len(chunk)
                print('\r' + update_bar(downloaded, target_size, LENGTH_BAR), end='')
        print("Finished! -> {}.mp4".format(video_title))

    def get_video_name(self):
        try:
            return self.__data["title"]
        except KeyError:
            raise KeyError("error: there is no video data available")
    
    def __save_info(self, info:dict):
        strip_stuff = lambda x: x.strip((ascii_letters + punctuation + ' ').replace('p', ''))
        if "mp4" in info["links"]:
            self.__data["title"] = info["title"]
            self.__data["vid"] = info["vid"]
            self.__data["qualities"] = {}
            for quality_data in info["links"]["mp4"].values():
                if quality_data["q"] != "auto" and quality_data["f"] == "mp4":
                    self.__data["qualities"][strip_stuff(quality_data["q"])] = Video(info["vid"],
                                                                                     quality_data["k"],
                                                                                     quality_data["size"] if quality_data["size"][0].isnumeric() else "??? MB",
                                                                                     )
            return True
        else:
            print("error: there is no video data available")
            return False

    def __analyze(self, url:str) -> dict:
        r = post(self.__host + self.__analyze_endpoint,
                 headers=self.__default_headers,
                 data="k_query={}".format(url))
        return r.json()

    def __convert(self, video:Video) -> dict:
        '''Le pregunta a la API por el link de descarga del video ingresado como parámetro'''
        r = post(self.__host + self.__convert_endpoint,
                 headers=self.__default_headers,
                 data="vid={}&k={}".format(video.id,
                                           video.key,
                                           ))
        return r.json()

    def __get_download_link(self, video:Video):
        try:
            return self.__convert(video)["dlink"].replace("\\/", "/")
        except KeyError:
            return ""

    def get_formatted_data(self, print_:bool=True):
        if not self.__check_data():
            raise ValueError("No hay datos!")
        d = pformat(self.__data)
        if print_:
            print(d)
        return d