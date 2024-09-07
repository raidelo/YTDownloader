from argparse import ArgumentParser
from pprint import pformat
from string import ascii_letters, punctuation
from requests import get, post

class Video:
    def __init__(self, id, key, size="??? MB", quality='none'):
        self.id = id
        self.key = key
        self.size = size
        self.quality = quality

    def __str__(self) -> str:
        return "Video {{ id: {id}, key: {key}, size: {size}, quality: {quality} }}".format(id=self.id,
                                                                                   key=self.key,
                                                                                   size=self.size,
                                                                                   quality=self.quality,
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
    __url_error = "error: url inválida"
    __missing_target_url = "error: no hay url objetivo"
    __missing_data_error = "error: no hay datos de vídeo disponibles"

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
            raise ValueError(self.__url_error)
        self.__target = url
    
    def reset_target(self):
        self.__target = ''
        self.__reset_data()

    def get_info(self):
        if not self.__check_target():
            raise Exception()
        info = self.__analyze(self.__target)
        return self.__save_info(info)

    def download(self, calidad):
        try:
            if isinstance(calidad, int):
                if not calidad in self.__data['qualities'].keys():
                    print("error: calidad no disponible -> {}".format(calidad))
                    exit(1)
            elif isinstance(calidad, str):
                calidad = int(calidad.strip('p'))
            vid = self.__data["qualities"][calidad]
        except KeyError:
            print("error: calidad no disponible -> {}".format(calidad))
            exit(1)
        self.__download(vid)
        self.reset_target()

    def __download(self, video):
        link = self.__get_download_link(video)
        response = get(link,
                       headers=self.__default_headers,
                       stream=True)
    
        def update_bar(done, target, length_bar):
            p = done / target
            buffer = '['
            asterisc = round(length_bar*p)
            buffer += '*'*asterisc + '-'*(length_bar - asterisc)
            buffer += '] {} % ({} MB / {} MB)'.format(round(p*100),
                                                      round(done / 1000000, 3),
                                                      round(target / 1000000, 3),
                                                      )
            return buffer

        video_title = self.get_video_name()
        LENGTH_BAR = 50
        CHUNK_SIZE = 1024
        iterator = response.iter_content(CHUNK_SIZE)
        downloaded = 0
        target_size = int(response.headers["Content-Length"].strip())
        with open(video_title+".mp4", "wb") as file:
            print("Downloading video: {}.mp4 ({})".format(video_title, video.quality))
            for chunk in iterator:
                file.write(chunk)
                downloaded += len(chunk)
                print('\r' + update_bar(downloaded, target_size, LENGTH_BAR), end='')
        print("Finished! -> {}.mp4".format(video_title))

    def get_video_name(self):
        try:
            return self.__data["title"]
        except KeyError:
            raise KeyError(self.__missing_data_error)
    
    def __save_info(self, info:dict):
        strip_stuff = lambda x: x.strip((ascii_letters + punctuation + ' '))
        if "links" not in info.keys():
            print("error: no hay contenido para descargar")
            return False
        elif "mp4" in info["links"]:
            self.__data["title"] = info["title"]
            self.__data["vid"] = info["vid"]
            self.__data["qualities"] = {}
            for quality_data in info["links"]["mp4"].values():
                if quality_data["q"] != "auto" and quality_data["f"] == "mp4":
                    self.__data["qualities"][int(strip_stuff(quality_data["q"]))] = Video(info["vid"],
                                                                                          quality_data["k"],
                                                                                          quality_data["size"] if quality_data["size"][0].isnumeric() else "??? MB",
                                                                                          quality_data["q"],
                                                                                          )
            return True
        else:
            print("error: no hay contenido para descargar")
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
            raise ValueError(self.__missing_data_error)
        d = pformat(self.__data)
        if print_:
            print(d)
        return d

    def print_available_qualities(self, add_choices:bool=False):
        if not self.__check_data():
            raise KeyError(self.__missing_data_error)
        qualities = self.__data["qualities"]
        list_of_qualities = [key for key in qualities.keys()]
        list_of_qualities.sort(reverse=True)
        print("{} de video disponible para descargar:".format("Calidades" if len(list_of_qualities) > 1 else "Calidad"))
        for pos, key in enumerate(list_of_qualities):
            print("{}{} -> {}".format("[{}] - ".format(pos+1) if add_choices else '', str(key)+'p', qualities[key].size))
        return tuple(list_of_qualities)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("link", nargs="?", default='',
                        help="el link del vídeo que quieres descargar")
    parser.add_argument("calidad", nargs="?", default='',
                        help="la calidad en la que prefieres descargar el vídeo")
    parser.add_argument("--stdin", action="store_true",
                        help="flag para ingresar tanto la url como la calidad por la entrada de datos estándar (stdin)")
    args = parser.parse_args()

    downloader = YTDownloader()

    if args.stdin:
        if args.link:
            parser.error("argument --stdin: not allowed with argument link or calidad")
        link = input("Ingrese el link: ").strip()
    elif args.link:
        link = args.link
    else:
        parser.print_help()
        exit(1)

    downloader.set_target(link)

    if not downloader.get_info():
        print("error: hubo un error al intentar obtener información del vídeo")
        exit(1)

    print("Link de vídeo detectado! -> {}".format(downloader.get_video_name()))

    if args.stdin:
        ammount_qualities = downloader.print_available_qualities(True)
        calidad = input("-> ").strip()
        try:
            number = int(calidad)
        except ValueError:
            print("Opción inválida")
            exit(1)
        if not (number > 0 and number <= len(ammount_qualities)):
            print("Opción inválida")
            exit(1)
        calidad = ammount_qualities[number]
    else:
        if not args.calidad:
            downloader.print_available_qualities()
            exit(1)
        else:
            calidad = args.calidad

    try:
        downloader.download(calidad if args.stdin else args.calidad)
    except KeyboardInterrupt:
        pass
    finally:
        exit(0)
